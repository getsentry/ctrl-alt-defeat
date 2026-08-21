"""Tests for name_generator.py"""

from name_generator import (
    ADJECTIVES,
    MAX_NAME_LENGTH,
    MIN_NAME_LENGTH,
    NOUNS,
    name_error,
    name_with_suffix,
    random_name,
)


class TestRandomName:
    def test_every_combination_is_a_legal_name(self):
        """The generator must never propose a name the validator refuses."""
        for adjective in ADJECTIVES:
            for noun in NOUNS:
                name = adjective + noun
                assert name_error(name) is None, f"{name} is not legal"

    def test_a_generated_name_is_legal(self):
        for _ in range(50):
            assert name_error(random_name()) is None


class TestNameWithSuffix:
    def test_the_number_is_kept_and_the_base_is_trimmed(self):
        assert name_with_suffix("SchedulerScheduler", 1234) == "SchedulerSchedul1234"

    def test_a_short_base_is_left_alone(self):
        assert name_with_suffix("Heap", 7) == "Heap7"

    def test_the_result_fits_the_limit(self):
        longest = max(ADJECTIVES, key=len) + max(NOUNS, key=len)
        assert len(name_with_suffix(longest, 9999)) <= MAX_NAME_LENGTH


class TestNameError:
    def test_a_plain_name_is_accepted(self):
        assert name_error("SilentPacket") is None

    def test_digits_and_punctuation_are_accepted(self):
        assert name_error("dan_f-2") is None

    def test_a_short_name_is_refused(self):
        assert name_error("ab") is not None
        assert name_error("abc") is None

    def test_a_long_name_is_refused(self):
        assert name_error("x" * MAX_NAME_LENGTH) is None
        assert name_error("x" * (MAX_NAME_LENGTH + 1)) is not None

    def test_a_space_is_refused(self):
        """A name with a space reads as two names in a leaderboard row."""
        assert name_error("Silent Packet") is not None

    def test_an_empty_name_is_refused(self):
        assert name_error("") is not None

    def test_the_limits_are_the_ones_the_message_names(self):
        assert str(MIN_NAME_LENGTH) in name_error("a")
        assert str(MAX_NAME_LENGTH) in name_error("x" * 99)
