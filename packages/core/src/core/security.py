import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from core.constants import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH

# Single reusable hasher; argon2-cffi's defaults follow the RFC 9106 / OWASP
# guidance (argon2id). Tune memory_cost/time_cost/parallelism here if the
# host's capacity planning ever requires it.
_hasher = PasswordHasher()


def hash_password(raw_password: str) -> str:
    """Hash a plaintext password into an argon2id encoded string (salt + params
    embedded). The result goes into User.password_hash."""
    return _hasher.hash(raw_password)


def verify_password(raw_password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, raw_password)
    except VerifyMismatchError:
        return False


def validate_password(password: str) -> None:
    """Raise ``ValueError`` if the password length is outside the configured
    bounds (``core.constants``). Length is the only password policy enforced.

    Callers translate the error to their own surface: the API relies on Pydantic
    ``Field`` bounds instead, while the CLI converts this to a ``SystemExit``.
    """
    if not (PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH):
        raise ValueError(
            f"password must be between {PASSWORD_MIN_LENGTH} and "
            f"{PASSWORD_MAX_LENGTH} characters."
        )


def generate_session_token() -> str:
    """A 256-bit CSPRNG token. This raw value goes into the cookie and is never
    stored; only its digest (hash_token) is persisted."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Deterministic SHA-256 hex digest of a session token. Deterministic (unlike
    argon2) because the token *is* the DB lookup key; fast/unsalted is safe
    because the token already carries 256 bits of entropy."""
    return hashlib.sha256(token.encode()).hexdigest()
