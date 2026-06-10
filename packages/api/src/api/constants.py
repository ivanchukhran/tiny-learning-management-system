"""API-layer constants.

Password policy lives here, not in `database`: the DB stores `password_hash`
as `Text` (no length), so these bounds are purely a request-validation concern.
"""

from datetime import timedelta

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128

# Session policy (ADR-019). Events are stored on the row; these windows are the
# policy applied at read time, so they can be retuned here without a migration.
SESSION_COOKIE_NAME = "session"
SESSION_IDLE_WINDOW = timedelta(hours=1)  # idle timeout
SESSION_MAX_LIFETIME = timedelta(hours=12)  # absolute ceiling -> forced re-login
# Lazy-bump: only push last_seen_at forward when it is at least this stale, so a
# read-heavy request load does not write on every call.
SESSION_BUMP_THRESHOLD = timedelta(minutes=5)
