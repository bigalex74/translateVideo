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


def _noop_mp3_to_wav(mp3_bytes: bytes, wav_path) -> None:
    """Тестовый заменитель: пишем fake-байты в wav_path без вызова ffmpeg."""
    wav_path.write_bytes(mp3_bytes)


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
        self._mp3_to_wav_patcher = patch(
            "translate_video.tts.openai_tts._mp3_to_wav", side_effect=_noop_mp3_to_wav
        )
        self._mp3_to_wav_patcher.start()

    def tearDown(self):
        self._mp3_to_wav_patcher.stop()
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
        """synthesize() создаёт wav файл и устанавливает tts_path."""
        provider, _ = self._make_provider()
        project = _make_project(self.work_dir)
        seg = _make_segment(0, "Создание файла")
        project.segments = [seg]

        provider.synthesize(project, project.segments)

        self.assertIsNotNone(seg.tts_path)
        wav = self.work_dir / seg.tts_path
        self.assertTrue(wav.exists())
        self.assertTrue(seg.tts_path.endswith(".wav"))

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



class OpenAIQaFlagsResetTest(unittest.TestCase):
    """TVIDEO-096: QA-флаги TTS сбрасываются при повторном запуске (OpenAI провайдер)."""

    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self._tmpdir.name)
        (self.work_dir / "tts").mkdir(parents=True, exist_ok=True)
        self._mp3_to_wav_patcher = patch(
            "translate_video.tts.openai_tts._mp3_to_wav", side_effect=_noop_mp3_to_wav
        )
        self._mp3_to_wav_patcher.start()

    def tearDown(self):
        self._mp3_to_wav_patcher.stop()
        self._tmpdir.cleanup()

    def _provider(self) -> OpenAITTSProvider:
        return OpenAITTSProvider(
            base_url="https://fake.api/v1",
            api_key="test",
            model="tts-1",
            voice_1="nova",
            voice_2="onyx",
            http_post=lambda *a, **kw: b"mp3",
        )

    def _seg_with_flags(self, flags: list[str]) -> Segment:
        s = Segment(id="s0", start=0.0, end=2.0, source_text="Hi")
        s.translated_text = "Привет"
        s.status = SegmentStatus.TRANSLATED
        s.qa_flags = list(flags)
        return s

    def test_stale_tts_flags_removed(self):
        """tts_openai_error и tts_voice_X удаляются перед новой озвучкой."""
        project = _make_project(self.work_dir)
        seg = self._seg_with_flags(["tts_openai_error", "tts_voice_onyx"])
        project.segments = [seg]

        self._provider().synthesize(project, project.segments)

        flags = project.segments[0].qa_flags
        self.assertNotIn("tts_openai_error", flags)
        self.assertNotIn("tts_voice_onyx", flags)

    def test_non_tts_flags_preserved(self):
        """timing_fit_* и translation_* флаги сохраняются при повторной озвучке."""
        project = _make_project(self.work_dir)
        seg = self._seg_with_flags([
            "timing_fit_failed",
            "translation_rewritten_for_timing",
            "tts_openai_error",  # должен удалиться
        ])
        project.segments = [seg]

        self._provider().synthesize(project, project.segments)

        flags = project.segments[0].qa_flags
        self.assertIn("timing_fit_failed", flags)
        self.assertIn("translation_rewritten_for_timing", flags)
        self.assertNotIn("tts_openai_error", flags)

    def test_new_voice_flag_replaces_old(self):
        """После сброса добавляется актуальный tts_voice_nova, старый tts_voice_fable удалён."""
        project = _make_project(self.work_dir, tts_voice="nova")
        seg = self._seg_with_flags(["tts_voice_fable"])
        project.segments = [seg]

        self._provider().synthesize(project, project.segments)

        flags = project.segments[0].qa_flags
        self.assertIn("tts_voice_nova", flags)
        self.assertNotIn("tts_voice_fable", flags)



class SynthPreviewTest(unittest.TestCase):
    """TVIDEO-133: synth_preview() возвращает MP3-байты с правильными параметрами."""

    def _provider(self, model="tts-1", openai_speed=1.0,
                  el_speed=1.0, el_stability=0.5, el_similarity_boost=0.75, el_style=0.0):
        http_post = MagicMock(return_value=b"mp3_bytes")
        p = OpenAITTSProvider(
            base_url="https://fake.api/v1",
            api_key="key",
            model=model,
            voice_1="nova",
            voice_2="onyx",
            openai_speed=openai_speed,
            el_speed=el_speed,
            el_stability=el_stability,
            el_similarity_boost=el_similarity_boost,
            el_style=el_style,
            http_post=http_post,
        )
        return p, http_post

    def test_returns_bytes_from_http_post(self):
        """synth_preview() возвращает то, что вернул _http_post."""
        provider, mock_post = self._provider()
        result = provider.synth_preview("Привет", "nova")
        self.assertEqual(result, b"mp3_bytes")
        mock_post.assert_called_once()

    def test_openai_default_speed_not_in_payload(self):
        """speed=1.0 (дефолт) не добавляется в payload для OpenAI."""
        provider, mock_post = self._provider(openai_speed=1.0)
        provider.synth_preview("Текст", "nova")
        payload = mock_post.call_args[0][1]
        self.assertNotIn("speed", payload)

    def test_openai_custom_speed_in_payload(self):
        """speed=1.3 добавляется в payload для OpenAI."""
        provider, mock_post = self._provider(openai_speed=1.3)
        provider.synth_preview("Текст", "nova")
        payload = mock_post.call_args[0][1]
        self.assertIn("speed", payload)
        self.assertAlmostEqual(payload["speed"], 1.3, places=4)

    def test_elevenlabs_params_in_payload(self):
        """ElevenLabs: el_speed, stability, similarity_boost, style попадают в payload."""
        provider, mock_post = self._provider(
            model="elevenlabs/turbo-v2",
            el_speed=1.1,
            el_stability=0.7,
            el_similarity_boost=0.8,
            el_style=0.2,
        )
        provider.synth_preview("Test", "Rachel")
        payload = mock_post.call_args[0][1]
        self.assertAlmostEqual(payload["speed"], 1.1, places=4)
        self.assertAlmostEqual(payload["stability"], 0.7, places=4)
        self.assertAlmostEqual(payload["similarity_boost"], 0.8, places=4)
        self.assertAlmostEqual(payload["style"], 0.2, places=4)

    def test_elevenlabs_no_openai_speed(self):
        """ElevenLabs модель: openai_speed НЕ добавляется (используется el_speed)."""
        provider, mock_post = self._provider(
            model="elevenlabs/turbo-v2",
            openai_speed=1.5,   # должен игнорироваться
            el_speed=1.0,
        )
        provider.synth_preview("Test", "Rachel")
        payload = mock_post.call_args[0][1]
        # speed в payload = el_speed=1.0 (не openai_speed)
        self.assertIn("speed", payload)
        self.assertAlmostEqual(payload["speed"], 1.0, places=4)

    def test_payload_base_fields(self):
        """Базовые поля model, input, voice, response_format всегда в payload."""
        provider, mock_post = self._provider()
        provider.synth_preview("Hello", "shimmer")
        payload = mock_post.call_args[0][1]
        self.assertEqual(payload["model"], "tts-1")
        self.assertEqual(payload["input"], "Hello")
        self.assertEqual(payload["voice"], "shimmer")
        self.assertEqual(payload["response_format"], "mp3")

    def test_authorization_header(self):
        """Authorization: Bearer key передаётся в заголовках."""
        provider, mock_post = self._provider()
        provider.synth_preview("Hi", "nova")
        headers = mock_post.call_args[1].get("headers") or mock_post.call_args[0][2]
        self.assertIn("Authorization", headers)
        self.assertIn("key", headers["Authorization"])


class Mp3ToWavTest(unittest.TestCase):
    """TVIDEO-130: _mp3_to_wav() конвертирует MP3-байты в WAV через ffmpeg.

    subprocess/tempfile/os импортируются локально внутри функции,
    поэтому патчим через глобальный модуль 'subprocess'.
    """

    def test_creates_wav_file(self):
        """_mp3_to_wav() вызывает ffmpeg с правильными аргументами."""
        import tempfile as _tempfile
        from translate_video.tts.openai_tts import _mp3_to_wav

        with patch("subprocess.run") as mock_run, \
                _tempfile.TemporaryDirectory() as tmpdir:
            mock_run.return_value = MagicMock(returncode=0)
            wav_path = Path(tmpdir) / "output.wav"

            _mp3_to_wav(b"fake_mp3_bytes", wav_path)

            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            self.assertEqual(cmd[0], "ffmpeg")
            self.assertIn("-ar", cmd)
            self.assertIn("44100", cmd)
            self.assertIn("-ac", cmd)
            self.assertIn("1", cmd)
            self.assertIn(str(wav_path), cmd)

    def test_ffmpeg_sample_rate_44100(self):
        """ffmpeg вызывается с -ar 44100 (исправление проблемы 24kHz→кряк)."""
        import tempfile as _tempfile
        from translate_video.tts.openai_tts import _mp3_to_wav

        with patch("subprocess.run") as mock_run, \
                _tempfile.TemporaryDirectory() as tmpdir:
            mock_run.return_value = MagicMock(returncode=0)
            _mp3_to_wav(b"data", Path(tmpdir) / "out.wav")

            args = mock_run.call_args[0][0]
            ar_idx = args.index("-ar")
            self.assertEqual(args[ar_idx + 1], "44100")

    def test_mono_channel(self):
        """ffmpeg вызывается с -ac 1 (моно)."""
        import tempfile as _tempfile
        from translate_video.tts.openai_tts import _mp3_to_wav

        with patch("subprocess.run") as mock_run, \
                _tempfile.TemporaryDirectory() as tmpdir:
            mock_run.return_value = MagicMock(returncode=0)
            _mp3_to_wav(b"data", Path(tmpdir) / "out.wav")

            args = mock_run.call_args[0][0]
            ac_idx = args.index("-ac")
            self.assertEqual(args[ac_idx + 1], "1")


if __name__ == "__main__":
    unittest.main()
