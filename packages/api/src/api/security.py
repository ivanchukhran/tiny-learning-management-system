from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

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
