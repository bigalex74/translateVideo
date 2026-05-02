"""TVIDEO-085: тесты OpenAITTSProvider.

Проверяет:
- synthesize() с mock HTTP — правильный URL, payload, voice mapping
- Стратегии single / two_voices / per_speaker
- Ошибки HTTP не роняют весь пайплайн (только QA-флаг)
- build_openai_tts_provider() возвращает None если нет ключа / провайдера
"""
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from translate_video.core.config import PipelineConfig, VoiceStrategy
from translate_video.core.schemas import Segment, SegmentStatus, VideoProject
from translate_video.tts.openai_tts import OpenAITTSProvider, build_openai_tts_provider


def _make_project(
    work_dir: Path,
    voice_strategy: str = "single",
    tts_provider: str = "neuroapi",
    tts_voice: str = "nova",
    tts_voice_2: str = "onyx",
) -> VideoProject:
    cfg = PipelineConfig()
    cfg.voice_strategy = VoiceStrategy(voice_strategy)
    cfg.professional_tts_provider = tts_provider
    cfg.professional_tts_model = "tts-1"
    cfg.professional_tts_voice = tts_voice
    cfg.professional_tts_voice_2 = tts_voice_2
    return VideoProject(
        id="tts_test",
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


class OpenAITTSProviderTest(unittest.TestCase):
    """TVIDEO-085: unit-тесты OpenAITTSProvider."""

    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self._tmpdir.name)
        (self.work_dir / "tts").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _make_provider(self, voice_1="nova", voice_2="onyx", http_post=None):
        if http_post is None:
            http_post = MagicMock(return_value=b"fake_mp3")
        return OpenAITTSProvider(
            base_url="https://neuroapi.host/v1",
            api_key="test_key",
            model="tts-1",
            voice_1=voice_1,
            voice_2=voice_2,
            http_post=http_post,
        ), http_post

    # ── Базовый вызов ─────────────────────────────────────────────────────────

    def test_synth_calls_correct_url(self):
        """synthesize() вызывает /audio/speech с правильным URL."""
        provider, mock_post = self._make_provider()
        project = _make_project(self.work_dir)
        project.segments = [_make_segment(0, "Привет")]

        provider.synthesize(project, project.segments)

        mock_post.assert_called_once()
        url = mock_post.call_args[0][0]
        self.assertIn("/audio/speech", url)

    def test_synth_payload_fields(self):
        """Payload содержит model, input, voice, response_format."""
        provider, mock_post = self._make_provider()
        project = _make_project(self.work_dir)
        project.segments = [_make_segment(0, "Тест синтеза")]

        provider.synthesize(project, project.segments)

        payload = mock_post.call_args[0][1]
        self.assertEqual(payload["model"], "tts-1")
        self.assertEqual(payload["input"], "Тест синтеза")
        self.assertEqual(payload["voice"], "nova")
        self.assertEqual(payload["response_format"], "mp3")

    def test_synth_creates_mp3_file(self):
        """synthesize() создаёт mp3 файл и устанавливает tts_path."""
        provider, _ = self._make_provider()
        project = _make_project(self.work_dir)
        seg = _make_segment(0, "Создание файла")
        project.segments = [seg]

        provider.synthesize(project, project.segments)

        self.assertIsNotNone(seg.tts_path)
        mp3 = self.work_dir / seg.tts_path
        self.assertTrue(mp3.exists())
        self.assertEqual(mp3.read_bytes(), b"fake_mp3")

    def test_empty_text_skipped(self):
        """Сегменты с пустым текстом пропускаются."""
        provider, mock_post = self._make_provider()
        project = _make_project(self.work_dir)
        project.segments = [_make_segment(0, "")]

        provider.synthesize(project, project.segments)

        mock_post.assert_not_called()

    # ── Стратегии голосов ─────────────────────────────────────────────────────

    def test_single_strategy_all_voice1(self):
        """single: все сегменты получают voice_1."""
        provider, mock_post = self._make_provider(voice_1="nova", voice_2="onyx")
        project = _make_project(self.work_dir, voice_strategy="single")
        project.segments = [_make_segment(i, f"Текст {i}") for i in range(3)]

        provider.synthesize(project, project.segments)

        calls = mock_post.call_args_list
        for call in calls:
            self.assertEqual(call[0][1]["voice"], "nova")

    def test_two_voices_strategy(self):
        """two_voices: чётные → voice_1 (nova), нечётные → voice_2 (onyx)."""
        provider, mock_post = self._make_provider(voice_1="nova", voice_2="onyx")
        project = _make_project(self.work_dir, voice_strategy="two_voices")
        project.segments = [_make_segment(i, f"Текст {i}") for i in range(4)]

        provider.synthesize(project, project.segments)

        calls = mock_post.call_args_list
        self.assertEqual(calls[0][0][1]["voice"], "nova")   # index 0 (чётный)
        self.assertEqual(calls[1][0][1]["voice"], "onyx")   # index 1 (нечётный)
        self.assertEqual(calls[2][0][1]["voice"], "nova")   # index 2 (чётный)
        self.assertEqual(calls[3][0][1]["voice"], "onyx")   # index 3 (нечётный)

    def test_per_speaker_strategy(self):
        """per_speaker: одинаковый speaker_id → одинаковый голос."""
        provider, mock_post = self._make_provider()
        project = _make_project(self.work_dir, voice_strategy="per_speaker")
        project.segments = [
            _make_segment(0, "Текст A", speaker_id="speaker_1"),
            _make_segment(1, "Текст B", speaker_id="speaker_2"),
            _make_segment(2, "Текст C", speaker_id="speaker_1"),  # снова speaker_1
        ]

        provider.synthesize(project, project.segments)

        calls = mock_post.call_args_list
        voice_s1_first  = calls[0][0][1]["voice"]
        voice_s2        = calls[1][0][1]["voice"]
        voice_s1_second = calls[2][0][1]["voice"]

        # speaker_1 всегда получает тот же голос
        self.assertEqual(voice_s1_first, voice_s1_second)
        # speaker_1 и speaker_2 получают разные голоса
        self.assertNotEqual(voice_s1_first, voice_s2)

    def test_voice_qa_flag_added(self):
        """Каждый сегмент получает QA-флаг с именем голоса."""
        provider, _ = self._make_provider(voice_1="shimmer")
        project = _make_project(self.work_dir, tts_voice="shimmer")
        seg = _make_segment(0, "Флаги QA")
        project.segments = [seg]

        provider.synthesize(project, project.segments)

        self.assertIn("tts_voice_shimmer", seg.qa_flags)

    # ── Обработка ошибок ──────────────────────────────────────────────────────

    def test_http_error_sets_qa_flag_not_raises(self):
        """HTTP ошибка при синтезе → QA-флаг tts_openai_error, не исключение."""
        def failing_post(*_, **__):
            raise RuntimeError("HTTP 429")

        provider, _ = self._make_provider(http_post=failing_post)
        project = _make_project(self.work_dir)
        seg = _make_segment(0, "Ошибка API")
        project.segments = [seg]

        # Не должно бросить исключение
        provider.synthesize(project, project.segments)
        self.assertIn("tts_openai_error", seg.qa_flags)
        self.assertIsNone(seg.tts_path)


class BuildOpenAITTSProviderTest(unittest.TestCase):
    """TVIDEO-085: тесты build_openai_tts_provider()."""

    def test_returns_none_if_no_provider(self):
        """Без professional_tts_provider → возвращает None."""
        cfg = PipelineConfig()
        cfg.professional_tts_provider = ""
        result = build_openai_tts_provider(cfg)
        self.assertIsNone(result)

    def test_returns_none_if_unknown_provider(self):
        """Неизвестный провайдер → None (нет в _PROVIDERS)."""
        cfg = PipelineConfig()
        cfg.professional_tts_provider = "unknown_provider"
        result = build_openai_tts_provider(cfg)
        self.assertIsNone(result)

    @patch.dict("os.environ", {"NEUROAPI_API_KEY": ""})
    def test_returns_none_if_no_api_key(self):
        """Нет API ключа → возвращает None."""
        cfg = PipelineConfig()
        cfg.professional_tts_provider = "neuroapi"
        result = build_openai_tts_provider(cfg)
        self.assertIsNone(result)

    @patch.dict("os.environ", {"NEUROAPI_API_KEY": "test_key_123"})
    def test_returns_provider_with_correct_config(self):
        """С ключом и провайдером → возвращает OpenAITTSProvider."""
        cfg = PipelineConfig()
        cfg.professional_tts_provider = "neuroapi"
        cfg.professional_tts_model = "tts-1-hd"
        cfg.professional_tts_voice = "shimmer"
        cfg.professional_tts_voice_2 = "fable"

        provider = build_openai_tts_provider(cfg)

        self.assertIsNotNone(provider)
        self.assertIsInstance(provider, OpenAITTSProvider)
        self.assertEqual(provider.model, "tts-1-hd")
        self.assertEqual(provider.voice_1, "shimmer")
        self.assertEqual(provider.voice_2, "fable")


if __name__ == "__main__":
    unittest.main()
