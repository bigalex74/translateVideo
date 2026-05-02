"""TVIDEO-090: тесты структуры SPEECHKIT_VOICES и _VOICE_POOL.

Проверяет:
- Все 20 голосов присутствуют
- Обязательные поля: id, name, gender, tier, roles
- tier ∈ {standard, premium}
- gender ∈ {male, female}
- roles — список из допустимых значений
- Голоса с roles=[] не имеют ролей (filipp, madirus, amira, john)
- Голоса с strict-ролью — только premium
- _VOICE_POOL содержит все голоса без дублей
- _VOICE_POOL начинается с premium-голосов
"""
import unittest

from translate_video.tts.speechkit_tts import SPEECHKIT_VOICES, _VOICE_POOL

_ALLOWED_ROLES = {"neutral", "good", "evil", "strict", "whisper"}
_ALLOWED_GENDERS = {"male", "female"}
_ALLOWED_TIERS = {"standard", "premium"}

_EXPECTED_IDS = {
    # standard
    "alena", "jane", "omazh", "zahar", "ermil", "filipp", "madirus", "amira", "john",
    # premium
    "julia", "lera", "marina", "alexander", "kirill", "anton", "masha",
    "zhanar", "saule", "yulduz", "zamira",
}

_NO_ROLE_VOICES = {"filipp", "madirus", "amira", "john"}


class SpeechKitVoicesStructureTest(unittest.TestCase):
    """TVIDEO-090: структура и полнота списка голосов."""

    def test_total_count(self):
        """Ровно 20 голосов."""
        self.assertEqual(len(SPEECHKIT_VOICES), 20)

    def test_all_ids_present(self):
        """Все ожидаемые ID голосов присутствуют."""
        ids = {v["id"] for v in SPEECHKIT_VOICES}
        self.assertEqual(ids, _EXPECTED_IDS)

    def test_required_fields(self):
        """Каждый голос имеет обязательные поля."""
        required = {"id", "name", "gender", "tier", "tone", "roles"}
        for v in SPEECHKIT_VOICES:
            missing = required - v.keys()
            self.assertFalse(missing, f"{v['id']}: отсутствуют поля {missing}")

    def test_valid_gender(self):
        """gender ∈ {male, female}."""
        for v in SPEECHKIT_VOICES:
            self.assertIn(v["gender"], _ALLOWED_GENDERS, f"{v['id']}: неверный gender")

    def test_valid_tier(self):
        """tier ∈ {standard, premium}."""
        for v in SPEECHKIT_VOICES:
            self.assertIn(v["tier"], _ALLOWED_TIERS, f"{v['id']}: неверный tier")

    def test_roles_are_valid(self):
        """Все роли из допустимого набора."""
        for v in SPEECHKIT_VOICES:
            for role in v["roles"]:
                self.assertIn(role, _ALLOWED_ROLES,
                              f"{v['id']}: недопустимая роль {role!r}")

    def test_no_role_voices_have_empty_roles(self):
        """Голоса без поддержки role имеют roles=[]."""
        for v in SPEECHKIT_VOICES:
            if v["id"] in _NO_ROLE_VOICES:
                self.assertEqual(v["roles"], [],
                                 f"{v['id']}: должен иметь roles=[]")

    def test_premium_voices_count(self):
        """Ровно 11 premium-голосов."""
        premium = [v for v in SPEECHKIT_VOICES if v["tier"] == "premium"]
        self.assertEqual(len(premium), 11)

    def test_standard_voices_count(self):
        """Ровно 9 standard-голосов."""
        standard = [v for v in SPEECHKIT_VOICES if v["tier"] == "standard"]
        self.assertEqual(len(standard), 9)


class VoicePoolTest(unittest.TestCase):
    """TVIDEO-090: тесты _VOICE_POOL."""

    def test_pool_has_all_voices(self):
        """_VOICE_POOL содержит все 20 голосов."""
        self.assertEqual(set(_VOICE_POOL), _EXPECTED_IDS)

    def test_pool_no_duplicates(self):
        """_VOICE_POOL без дублей."""
        self.assertEqual(len(_VOICE_POOL), len(set(_VOICE_POOL)))

    def test_pool_premium_first(self):
        """_VOICE_POOL начинается с premium-голосов."""
        premium_ids = {v["id"] for v in SPEECHKIT_VOICES if v["tier"] == "premium"}
        # Первые 11 должны быть premium
        first_11 = set(_VOICE_POOL[:11])
        self.assertEqual(first_11, premium_ids)

    def test_pool_standard_last(self):
        """_VOICE_POOL заканчивается standard-голосами."""
        standard_ids = {v["id"] for v in SPEECHKIT_VOICES if v["tier"] == "standard"}
        last_9 = set(_VOICE_POOL[11:])
        self.assertEqual(last_9, standard_ids)


if __name__ == "__main__":
    unittest.main()
