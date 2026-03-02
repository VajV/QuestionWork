"""Tests for password complexity validation on UserCreate."""

import pytest
from pydantic import ValidationError

from app.models.user import UserCreate


def _make_payload(**overrides):
    """Build a valid UserCreate dict, then apply overrides."""
    base = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "SecurePass1!",
        "role": "freelancer",
    }
    base.update(overrides)
    return base


class TestPasswordComplexity:
    """Validate that UserCreate enforces password rules."""

    def test_valid_password(self):
        user = UserCreate(**_make_payload(password="GoodPass1!"))
        assert user.password == "GoodPass1!"

    def test_missing_uppercase(self):
        with pytest.raises(ValidationError, match="uppercase"):
            UserCreate(**_make_payload(password="nouppercase1!"))

    def test_missing_digit(self):
        with pytest.raises(ValidationError, match="digit"):
            UserCreate(**_make_payload(password="NoDigitHere!"))

    def test_missing_special_char(self):
        with pytest.raises(ValidationError, match="special"):
            UserCreate(**_make_payload(password="NoSpecial1"))

    def test_too_short(self):
        with pytest.raises(ValidationError):
            UserCreate(**_make_payload(password="A1!"))

    def test_too_long(self):
        with pytest.raises(ValidationError):
            UserCreate(**_make_payload(password="A1!" + "x" * 126))

    def test_all_requirements_met(self):
        user = UserCreate(**_make_payload(password="MyP@ss99"))
        assert user.password == "MyP@ss99"

    def test_special_chars_variety(self):
        """Various special characters should be accepted."""
        for char in ["!", "@", "#", "$", "%", "^", "&", "*"]:
            pwd = f"TestPass1{char}"
            user = UserCreate(**_make_payload(password=pwd))
            assert user.password == pwd
