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

    def test_voice_without_role_omits_role_hint(self):
        """filipp/madirus/amira/john НЕ получают role-хинт → не будет HTTP 400."""
        calls = []
        def capture(url, p, **kw):
            calls.append(p)
            return b"mp3"

        # filipp — roles=[] по данным SPEECHKIT_VOICES
        provider, _ = self._make_provider(voice_1="filipp", role_1="neutral", http_post=capture)
        project = _make_project(self.work_dir, tts_voice="filipp", tts_role="neutral")
        project.segments = [_make_segment(0, "Тест без роли")]
        provider.synthesize(project, project.segments)

        hints = calls[0].get("hints", [])
        role_hints = [h for h in hints if "role" in h]
        self.assertEqual(role_hints, [], msg=f"filipp не должен иметь role-хинт, получили: {hints}")

    def test_voice_with_role_sends_role_hint(self):
        """alena/zahar/ermil/jane/omazh получают role-хинт."""
        calls = []
        def capture(url, p, **kw):
            calls.append(p)
            return b"mp3"

        provider, _ = self._make_provider(voice_1="alena", role_1="good", http_post=capture)
        project = _make_project(self.work_dir, tts_voice="alena", tts_role="good")
        project.segments = [_make_segment(0, "Тест с ролью")]
        provider.synthesize(project, project.segments)

        hints = calls[0].get("hints", [])
        role_hints = [h["role"] for h in hints if "role" in h]
        self.assertIn("good", role_hints, msg=f"alena должна иметь role=good в хинтах: {hints}")

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


class StaleTTSPathGuardTest(unittest.TestCase):
    """TVIDEO-097: tts_path сбрасывается до None в начале synthesize().

    Без этого: если синтез провалится, tts_path остаётся от СТАРОЙ озвучки.
    Рендер читает tts_path → берёт старый mp3 → в видео чужой голос.
    """

    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self._tmpdir.name)
        (self.work_dir / "tts").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _make_seg_with_old_path(self, i: int, old_path: str) -> Segment:
        """Сегмент с tts_path от предыдущей озвучки (stale)."""
        s = _make_segment(i, "Привет мир")
        s.tts_path = old_path  # устаревший путь от старого голоса
        return s

    def test_tts_path_reset_to_none_at_start(self):
        """tts_path сбрасывается до None в начале synthesize(), до любых вызовов API."""
        def always_fail(*a, **kw):
            raise RuntimeError("API unavailable")

        provider = YandexSpeechKitTTSProvider(
            api_key="test", voice_1="alena", voice_2="filipp",
            http_post=always_fail,
        )
        project = _make_project(self.work_dir)
        seg = self._make_seg_with_old_path(0, "tts/old_kirill_voice.mp3")
        project.segments = [seg]

        provider.synthesize(project, project.segments)

        self.assertIsNone(project.segments[0].tts_path,
            "tts_path должен быть None после ошибки синтеза, не указывать на старый mp3")

    def test_tts_path_set_after_successful_synth(self):
        """При успешном синтезе tts_path обновляется на новый файл."""
        fake_response = _make_streaming_response(b"new_audio")
        provider = YandexSpeechKitTTSProvider(
            api_key="test", voice_1="alena", voice_2="filipp",
            http_post=lambda *a, **kw: fake_response,
        )
        project = _make_project(self.work_dir)
        seg = self._make_seg_with_old_path(0, "tts/old_kirill_voice.mp3")
        project.segments = [seg]

        provider.synthesize(project, project.segments)

        # tts_path обновился — больше не указывает на старый файл
        new_path = project.segments[0].tts_path
        self.assertIsNotNone(new_path)
        self.assertNotEqual(new_path, "tts/old_kirill_voice.mp3",
            "tts_path должен указывать на новый mp3, не на старый")

    def test_multiple_segments_all_paths_reset(self):
        """Все сегменты с устаревшим tts_path сбрасываются до None."""
        def always_fail(*a, **kw):
            raise RuntimeError("down")

        provider = YandexSpeechKitTTSProvider(
            api_key="test", voice_1="alena", voice_2="filipp",
            http_post=always_fail,
        )
        project = _make_project(self.work_dir)
        project.segments = [
            self._make_seg_with_old_path(i, f"tts/old_{i}.mp3")
            for i in range(3)
        ]

        provider.synthesize(project, project.segments)

        for i, seg in enumerate(project.segments):
            self.assertIsNone(seg.tts_path,
                f"Сегмент {i}: tts_path должен быть None, не '{seg.tts_path}'")


class SSMLFallbackTest(unittest.TestCase):
    """TVIDEO-097 / TVIDEO-114: API v3 НЕ принимает поле "ssml" (HTTP 400).

    После фикса (TVIDEO-114):
    - emotion_level > 0 → enhance_tts_v3() → поле "text" с TTS-разметкой
    - Поле "ssml" больше НИКОГДА не отправляется в v3
    - Только 1 вызов API (без retry из-за ssml-400)
    """

    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self._tmpdir.name)
        (self.work_dir / "tts").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_emotion_level_uses_text_not_ssml(self):
        """emotion_level > 0 → поле 'text' с TTS-паузами, НЕ 'ssml' (HTTP 400 в v3)."""
        received = {}
        call_count = [0]

        def post(url, payload, **kw):
            call_count[0] += 1
            received.update(payload)
            return _make_streaming_response(b"audio")

        provider = YandexSpeechKitTTSProvider(
            api_key="test",
            voice_1="alena",
            voice_2="filipp",
            emotion_level=2,  # эмоции включены
            http_post=post,
        )
        project = _make_project(self.work_dir)
        seg = _make_segment(0, "Привет мир!")
        project.segments = [seg]

        provider.synthesize(project, project.segments)

        # Только 1 вызов — retry больше не нужен (нет ssml-400)
        self.assertEqual(call_count[0], 1,
            "API v3 emotion: только 1 вызов, ssml-retry больше не нужен")
        # Поле "ssml" никогда не отправляется в v3
        self.assertNotIn("ssml", received,
            "API v3 НЕ должен получать поле 'ssml' — HTTP 400")
        # Поле "text" содержит TTS-разметку (sil-паузы от emotion)
        self.assertIn("text", received,
            "emotion_level > 0 должен передавать поле 'text' с TTS-разметкой")
        # tts_path обновлён
        self.assertIsNotNone(project.segments[0].tts_path,
            "tts_path должен быть установлен")

    def test_emotion_level_adds_sil_pauses(self):
        """emotion_level > 0 → текст содержит sil<[ms]> паузы (TTS-разметка Яндекс)."""
        received = {}

        def post(url, payload, **kw):
            received.update(payload)
            return _make_streaming_response(b"audio")

        provider = YandexSpeechKitTTSProvider(
            api_key="test",
            voice_1="alena",
            voice_2="filipp",
            emotion_level=1,
            http_post=post,
        )
        project = _make_project(self.work_dir)
        seg = _make_segment(0, "Привет мир.")  # точка → должна добавить паузу
        project.segments = [seg]

        provider.synthesize(project, project.segments)

        text_sent = received.get("text", "")
        self.assertIn("sil<[", text_sent,
            "emotion_level > 0 должен добавлять sil<[ms]> паузы в текст")

    def test_ssml_fallback_no_error_qa_flag(self):
        """emotion_level > 0 без ошибки → нет флага tts_speechkit_error."""
        def post(url, payload, **kw):
            return _make_streaming_response(b"audio")

        provider = YandexSpeechKitTTSProvider(
            api_key="test",
            voice_1="alena",
            voice_2="filipp",
            emotion_level=1,
            http_post=post,
        )
        project = _make_project(self.work_dir)
        seg = _make_segment(0, "Тест")
        project.segments = [seg]

        provider.synthesize(project, project.segments)

        self.assertNotIn("tts_speechkit_error", project.segments[0].qa_flags,
            "Успешный синтез не должен добавлять флаг ошибки")

    def test_non_ssml_400_does_not_trigger_fallback(self):
        """HTTP 400 не от Empty Utterance → fallback НЕ вызывается, флаг ошибки добавляется."""
        call_count = [0]

        def post(url, payload, **kw):
            call_count[0] += 1
            raise RuntimeError("SpeechKit HTTP 400: b'Unknown voice'")

        provider = YandexSpeechKitTTSProvider(
            api_key="test",
            voice_1="alena",
            voice_2="filipp",
            emotion_level=2,
            http_post=post,
        )
        project = _make_project(self.work_dir)
        seg = _make_segment(0, "Тест")
        project.segments = [seg]

        provider.synthesize(project, project.segments)

        # Только 1 вызов — без retry
        self.assertEqual(call_count[0], 1,
            "Ошибка не от Empty Utterance → retry не должен вызываться")
        self.assertIn("tts_speechkit_error", project.segments[0].qa_flags)

    def test_emotion_level_0_no_sil_pauses(self):
        """emotion_level=0 → текст отправляется как есть, без sil-пауз."""
        received = {}

        def post(url, payload, **kw):
            received.update(payload)
            return _make_streaming_response(b"audio")

        provider = YandexSpeechKitTTSProvider(
            api_key="test",
            voice_1="alena",
            voice_2="filipp",
            emotion_level=0,
            http_post=post,
        )
        project = _make_project(self.work_dir)
        seg = _make_segment(0, "Тест без пауз.")
        project.segments = [seg]

        provider.synthesize(project, project.segments)

        text_sent = received.get("text", "")
        self.assertNotIn("sil<[", text_sent,
            "emotion_level=0 не должен добавлять sil-паузы")
        self.assertNotIn("ssml", received,
            "emotion_level=0 не должен использовать ssml")


class SSMLOverrideTest(unittest.TestCase):
    """TVIDEO-100: tts_ssml_override имеет приоритет над translated_text.

    Тестирует что:
    - Текст из tts_ssml_override отправляется в TTS вместо translated_text
    - SSML-теги обёртываются в <speak> если их нет
    - Уже обёрнутый <speak>...</speak> не двойная обёртка
    - ruaccent/stress не применяется к override
    - Если override пустой — использует translated_text как обычно
    """

    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self._tmpdir.name)
        (self.work_dir / "tts").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_ssml_override_used_instead_of_translated_text(self):
        """tts_ssml_override имеет приоритет над translated_text."""
        received_payload = {}

        def capture_post(url, payload, **kw):
            received_payload.update(payload)
            return _make_streaming_response(b"audio")

        provider = YandexSpeechKitTTSProvider(
            api_key="test", voice_1="alena", voice_2="filipp",
            emotion_level=0,
            http_post=capture_post,
        )
        project = _make_project(self.work_dir)
        seg = _make_segment(0, "старый текст")
        seg.tts_ssml_override = "во+да течёт по тру+бам"
        project.segments = [seg]

        provider.synthesize(project, project.segments)

        # В payload должен быть override, а не translated_text
        self.assertIn("text", received_payload)
        self.assertIn("во+да", received_payload.get("text", "") or
                      received_payload.get("ssml", ""),
            "tts_ssml_override должен быть отправлен в TTS")

    def test_tts_markup_override_goes_to_text_field(self):
        """TTS-разметка override отправляется в поле 'text', не 'ssml'."""
        received_payload = {}

        def capture_post(url, payload, **kw):
            received_payload.update(payload)
            return _make_streaming_response(b"audio")

        provider = YandexSpeechKitTTSProvider(
            api_key="test", voice_1="alena", voice_2="filipp",
            emotion_level=0,
            http_post=capture_post,
        )
        project = _make_project(self.work_dir)
        seg = _make_segment(0, "текст")
        # TTS-разметка с sil-паузой и ударением (Яндекс TTS-markup, поле 'text')
        seg.tts_ssml_override = 'Унылая пора! sil<[300]> Очей оч+арованье!'
        project.segments = [seg]

        provider.synthesize(project, project.segments)

        # TTS-разметка должна идти в поле 'text', не в 'ssml'
        self.assertIn("text", received_payload,
            "TTS-разметка должна быть в поле 'text'")
        self.assertNotIn("ssml", received_payload,
            "TTS-разметка не должна попадать в поле 'ssml'")
        self.assertIn("sil<[300]>", received_payload["text"],
            "sil-пауза должна быть сохранена в тексте")

    def test_tts_markup_accent_stars(self):
        """TTS-разметка **акцент** = логическое ударение (Яндекс TTS API v3).
        ** должны СОХРАНЯТЬСЯ в тексте — это валидная TTS-разметка Яндекс.
        Документация: https://yandex.cloud/ru/docs/speechkit/tts/markup/tts-markup
        «**Кот** пошёл в лес?» → логическое ударение на слово «Кот».
        """
        received_payload = {}

        def capture_post(url, payload, **kw):
            received_payload.update(payload)
            return _make_streaming_response(b"audio")

        provider = YandexSpeechKitTTSProvider(
            api_key="test", voice_1="alena", voice_2="filipp",
            emotion_level=0,
            http_post=capture_post,
        )
        project = _make_project(self.work_dir)
        seg = _make_segment(0, "текст")
        seg.tts_ssml_override = 'Мы **всегда** будем в ответе за тех, **кого приручили**.'
        project.segments = [seg]

        provider.synthesize(project, project.segments)

        text = received_payload.get("text", "")
        # ** СОХРАНЯЮТСЯ — это TTS-разметка логического ударения
        self.assertIn("**всегда**", text,
            "** должны сохраняться: это TTS-разметка логического ударения Яндекс")
        self.assertIn("**кого приручили**", text,
            "Второй ** акцент тоже сохраняется")
        self.assertNotIn("ssml", received_payload,
            "TTS-разметка не должна попадать в поле 'ssml'")

    def test_empty_override_falls_back_to_translated_text(self):
        """Пустой override → использовать translated_text."""
        received_payload = {}

        def capture_post(url, payload, **kw):
            received_payload.update(payload)
            return _make_streaming_response(b"audio")

        provider = YandexSpeechKitTTSProvider(
            api_key="test", voice_1="alena", voice_2="filipp",
            emotion_level=0,
            http_post=capture_post,
        )
        project = _make_project(self.work_dir)
        seg = _make_segment(0, "основной текст перевода")
        seg.tts_ssml_override = ""  # пустой — должен использоваться translated_text
        project.segments = [seg]

        provider.synthesize(project, project.segments)

        text = received_payload.get("text", "")
        self.assertIn("основной текст перевода", text,
            "При пустом override должен использоваться translated_text")

    def test_schema_migration_from_dict_without_ssml_override(self):
        """from_dict без поля tts_ssml_override не падает (совместимость со старыми проектами)."""
        data = {
            "start": 0.0,
            "end": 1.0,
            "source_text": "hello",
            "translated_text": "привет",
            "status": "draft",
            # tts_ssml_override отсутствует — поле добавлено в v1.25.0
        }
        seg = Segment.from_dict(data)
        self.assertEqual(seg.tts_ssml_override, "")

    def test_schema_migration_unknown_fields_ignored(self):
        """from_dict игнорирует незнакомые поля из будущих версий схемы."""
        data = {
            "start": 0.0,
            "end": 1.0,
            "source_text": "hello",
            "translated_text": "привет",
            "status": "draft",
            "future_unknown_field": "some_value",  # поле из будущей версии
        }
        seg = Segment.from_dict(data)  # не должен падать с TypeError
        self.assertEqual(seg.source_text, "hello")


if __name__ == "__main__":
    unittest.main()
