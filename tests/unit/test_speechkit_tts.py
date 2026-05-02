"""TVIDEO-086: тесты YandexSpeechKitTTSProvider.

Проверяет:
- POST к SPEECHKIT_TTS_URL с правильными полями
- voice/role mapping для single / two_voices / per_speaker
- Сборка streaming NDJSON ответа в mp3
- Ошибки не бросают исключение — только QA-флаг
- build_speechkit_tts_provider: нет ключа → None; есть ключ → провайдер
"""
import base64
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from translate_video.core.config import PipelineConfig, VoiceStrategy
from translate_video.core.schemas import Segment, SegmentStatus, VideoProject
from translate_video.tts.speechkit_tts import (
    SPEECHKIT_TTS_URL,
    YandexSpeechKitTTSProvider,
    build_speechkit_tts_provider,
)


def _make_project(
    work_dir: Path,
    voice_strategy: str = "single",
    tts_voice: str = "alena",
    tts_voice_2: str = "filipp",
    tts_role: str = "neutral",
    tts_role_2: str = "neutral",
) -> VideoProject:
    cfg = PipelineConfig()
    cfg.voice_strategy = VoiceStrategy(voice_strategy)
    cfg.professional_tts_provider = "yandex"
    cfg.professional_tts_voice = tts_voice
    cfg.professional_tts_voice_2 = tts_voice_2
    cfg.professional_tts_role = tts_role
    cfg.professional_tts_role_2 = tts_role_2
    return VideoProject(
        id="sk_test",
        input_video=Path("test.mp4"),
        work_dir=work_dir,
        config=cfg,
    )


def _make_segment(i: int, text: str = "Тест", speaker_id: str | None = None) -> Segment:
    s = Segment(id=f"seg_{i}", start=float(i), end=float(i + 2), source_text="Test")
    s.translated_text = text
    s.speaker_id = speaker_id
    s.status = SegmentStatus.TRANSLATED
    return s


def _make_streaming_response(*audio_chunks: bytes) -> bytes:
    """Имитирует NDJSON streaming ответ SpeechKit."""
    lines = []
    for chunk in audio_chunks:
        obj = {"audioChunk": {"data": base64.b64encode(chunk).decode()}}
        lines.append(json.dumps(obj).encode())
    return b"\n".join(lines)


class YandexSpeechKitTTSProviderTest(unittest.TestCase):
    """TVIDEO-086: unit-тесты YandexSpeechKitTTSProvider."""

    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self._tmpdir.name)
        (self.work_dir / "tts").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _make_provider(self, voice_1="alena", voice_2="filipp", role_1="neutral", role_2="neutral", http_post=None):
        """Создать провайдер с mock HTTP."""
        if http_post is None:
            fake_response = _make_streaming_response(b"mp3_chunk1", b"mp3_chunk2")
            http_post = lambda *a, **kw: fake_response  # noqa: E731
        return YandexSpeechKitTTSProvider(
            api_key="test_key",
            voice_1=voice_1,
            voice_2=voice_2,
            role_1=role_1,
            role_2=role_2,
            http_post=http_post,
        ), http_post

    # ── Базовый вызов ─────────────────────────────────────────────────────────

    def test_synth_calls_speechkit_url(self):
        """synthesize() отправляет POST на SPEECHKIT_TTS_URL."""
        calls = []
        def capture_post(url, payload, **kw):
            calls.append((url, payload))
            return _make_streaming_response(b"audio")

        provider, _ = self._make_provider(http_post=capture_post)
        project = _make_project(self.work_dir)
        project.segments = [_make_segment(0, "Привет, мир!")]

        provider.synthesize(project, project.segments)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], SPEECHKIT_TTS_URL)

    def test_synth_payload_has_text_and_hints(self):
        """Payload содержит text, hints с voice и role."""
        calls = []
        def capture(url, payload, **kw):
            calls.append(payload)
            return _make_streaming_response(b"audio")

        provider, _ = self._make_provider(voice_1="alena", role_1="good", http_post=capture)
        project = _make_project(self.work_dir, tts_voice="alena", tts_role="good")
        seg = _make_segment(0, "Тест payload")
        project.segments = [seg]
        provider.synthesize(project, project.segments)

        p = calls[0]
        self.assertEqual(p["text"], "Тест payload")
        voices_in_hints = [h.get("voice") for h in p.get("hints", [])]
        roles_in_hints  = [h.get("role")  for h in p.get("hints", [])]
        self.assertIn("alena", voices_in_hints)
        self.assertIn("good",  roles_in_hints)

    def test_synth_creates_mp3_from_base64_chunks(self):
        """Провайдер сохраняет mp3 байты которые вернул http_post (уже собранные)."""
        expected = b"chunk_a" + b"chunk_b" + b"chunk_c"
        provider, _ = self._make_provider(
            http_post=lambda *a, **kw: expected
        )
        project = _make_project(self.work_dir)
        seg = _make_segment(0, "Стриминг")
        project.segments = [seg]

        provider.synthesize(project, project.segments)

        mp3 = self.work_dir / seg.tts_path
        self.assertTrue(mp3.exists())
        self.assertEqual(mp3.read_bytes(), expected)

    def test_empty_text_skipped(self):
        """Пустые сегменты пропускаются."""
        calls = []
        provider, _ = self._make_provider(
            http_post=lambda *a, **kw: calls.append(1) or _make_streaming_response(b"x")
        )
        project = _make_project(self.work_dir)
        project.segments = [_make_segment(0, "")]
        provider.synthesize(project, project.segments)
        self.assertEqual(calls, [])

    def test_auth_header_is_api_key(self):
        """Authorization: Api-Key <key>."""
        headers_seen = []
        def capture(url, payload, **kw):
            headers_seen.append(kw.get("headers", {}))
            return _make_streaming_response(b"x")

        provider, _ = self._make_provider(http_post=capture)
        project = _make_project(self.work_dir)
        project.segments = [_make_segment(0, "Заголовок")]
        provider.synthesize(project, project.segments)

        auth = headers_seen[0].get("Authorization", "")
        self.assertTrue(auth.startswith("Api-Key "), msg=f"Got: {auth}")

    # ── Стратегии голосов ─────────────────────────────────────────────────────

    def test_single_all_voice1_role1(self):
        """single: все сегменты → voice_1 + role_1."""
        calls = []
        def capture(url, p, **kw):
            calls.append(p)
            return _make_streaming_response(b"x")

        provider, _ = self._make_provider(voice_1="zahar", role_1="good", http_post=capture)
        project = _make_project(self.work_dir, voice_strategy="single")
        project.segments = [_make_segment(i, f"Текст {i}") for i in range(3)]
        provider.synthesize(project, project.segments)

        for p in calls:
            voices = [h.get("voice") for h in p["hints"]]
            roles  = [h.get("role")  for h in p["hints"]]
            self.assertIn("zahar", voices)
            self.assertIn("good", roles)

    def test_two_voices_alternates(self):
        """two_voices: чётные → voice_1, нечётные → voice_2."""
        calls = []
        def capture(url, p, **kw):
            calls.append(p)
            return _make_streaming_response(b"x")

        provider, _ = self._make_provider(voice_1="alena", voice_2="filipp", http_post=capture)
        project = _make_project(self.work_dir, voice_strategy="two_voices")
        project.segments = [_make_segment(i, f"T{i}") for i in range(4)]
        provider.synthesize(project, project.segments)

        def get_voice(p):
            return next(h["voice"] for h in p["hints"] if "voice" in h)

        self.assertEqual(get_voice(calls[0]), "alena")
        self.assertEqual(get_voice(calls[1]), "filipp")
        self.assertEqual(get_voice(calls[2]), "alena")
        self.assertEqual(get_voice(calls[3]), "filipp")

    def test_per_speaker_same_speaker_same_voice(self):
        """per_speaker: один speaker_id → один голос каждый раз."""
        calls = []
        def capture(url, p, **kw):
            calls.append(p)
            return _make_streaming_response(b"x")

        provider, _ = self._make_provider(http_post=capture)
        project = _make_project(self.work_dir, voice_strategy="per_speaker")
        project.segments = [
            _make_segment(0, "A", speaker_id="sp1"),
            _make_segment(1, "B", speaker_id="sp2"),
            _make_segment(2, "C", speaker_id="sp1"),
        ]
        provider.synthesize(project, project.segments)

        def get_voice(p):
            return next(h["voice"] for h in p["hints"] if "voice" in h)

        self.assertEqual(get_voice(calls[0]), get_voice(calls[2]))  # sp1 consistent
        self.assertNotEqual(get_voice(calls[0]), get_voice(calls[1]))  # sp1 ≠ sp2

    # ── QA флаги ─────────────────────────────────────────────────────────────

    def test_qa_flags_set_on_success(self):
        """После синтеза: флаги tts_voice_<voice> и tts_speechkit."""
        provider, _ = self._make_provider(voice_1="ermil")
        project = _make_project(self.work_dir, tts_voice="ermil")
        seg = _make_segment(0, "QA флаги")
        project.segments = [seg]
        provider.synthesize(project, project.segments)
        self.assertIn("tts_voice_ermil", seg.qa_flags)
        self.assertIn("tts_speechkit", seg.qa_flags)

    def test_http_error_sets_flag_no_exception(self):
        """HTTP ошибка → QA-флаг tts_speechkit_error, не исключение."""
        def fail(*a, **kw): raise RuntimeError("HTTP 503")
        provider, _ = self._make_provider(http_post=fail)
        project = _make_project(self.work_dir)
        seg = _make_segment(0, "Ошибка API")
        project.segments = [seg]
        provider.synthesize(project, project.segments)
        self.assertIn("tts_speechkit_error", seg.qa_flags)
        self.assertIsNone(seg.tts_path)


class BuildSpeechKitProviderTest(unittest.TestCase):
    """TVIDEO-086: тесты build_speechkit_tts_provider()."""

    def test_returns_none_if_provider_not_yandex(self):
        cfg = PipelineConfig()
        cfg.professional_tts_provider = "neuroapi"
        self.assertIsNone(build_speechkit_tts_provider(cfg))

    def test_returns_none_if_no_provider(self):
        cfg = PipelineConfig()
        cfg.professional_tts_provider = ""
        self.assertIsNone(build_speechkit_tts_provider(cfg))

    @patch.dict("os.environ", {"YANDEX_SPEECHKIT_API_KEY": ""})
    def test_returns_none_if_no_key(self):
        cfg = PipelineConfig()
        cfg.professional_tts_provider = "yandex"
        self.assertIsNone(build_speechkit_tts_provider(cfg))

    @patch.dict("os.environ", {"YANDEX_SPEECHKIT_API_KEY": "secret_key"})
    def test_returns_provider_with_correct_config(self):
        cfg = PipelineConfig()
        cfg.professional_tts_provider = "yandex"
        cfg.professional_tts_voice = "jane"
        cfg.professional_tts_voice_2 = "zahar"
        cfg.professional_tts_role = "good"
        cfg.professional_tts_role_2 = "neutral"

        provider = build_speechkit_tts_provider(cfg)

        self.assertIsNotNone(provider)
        self.assertIsInstance(provider, YandexSpeechKitTTSProvider)
        self.assertEqual(provider.voice_1, "jane")
        self.assertEqual(provider.voice_2, "zahar")
        self.assertEqual(provider.role_1, "good")


if __name__ == "__main__":
    unittest.main()
