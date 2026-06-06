"""API-layer constants.

Password policy lives here, not in `database`: the DB stores `password_hash`
as `Text` (no length), so these bounds are purely a request-validation concern.
"""

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
