import pytest
from core.constants import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH
from core.security import validate_password


def test_validate_password_accepts_min_length():
    validate_password("x" * PASSWORD_MIN_LENGTH)  # no raise


def test_validate_password_accepts_max_length():
    validate_password("x" * PASSWORD_MAX_LENGTH)  # no raise


def test_validate_password_rejects_too_short():
    with pytest.raises(ValueError):
        validate_password("x" * (PASSWORD_MIN_LENGTH - 1))


def test_validate_password_rejects_too_long():
    with pytest.raises(ValueError):
        validate_password("x" * (PASSWORD_MAX_LENGTH + 1))


def test_validate_password_error_mentions_bounds():
    with pytest.raises(ValueError) as exc:
        validate_password("")
    message = str(exc.value)
    assert str(PASSWORD_MIN_LENGTH) in message
    assert str(PASSWORD_MAX_LENGTH) in message
