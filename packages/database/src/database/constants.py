"""Shared column-length constants.

Single source of truth for the `User` column lengths so the model's
`String(...)` and the Pydantic schemas' `max_length` cannot drift. Lives in
`database` because `api` depends on it (never the reverse).
"""

FIRST_NAME_MAX_LENGTH = 100
LAST_NAME_MAX_LENGTH = 100
COURSE_NAME_LENGTH = COURSE_DESCRIPTION_LENGTH = EMAIL_MAX_LENGTH = 255
COURSE_SLUG_LENGTH = 32

# Width of a session token hash at rest: SHA-256 as a hex digest is 64 chars.
SESSION_HASH_LENGTH = 64
