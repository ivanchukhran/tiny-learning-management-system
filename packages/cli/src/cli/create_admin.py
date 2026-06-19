import argparse
import asyncio
import getpass
import os

from core.security import hash_password, validate_password
from database.connection import get_sessionmaker
from database.repositories import create_or_promote_admin
from dotenv import load_dotenv
from sqlalchemy.exc import IntegrityError


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="create-admin",
        description=(
            "Create a new admin user, or promote an existing one to admin. "
            "An existing user is promoted without changing their password."
        ),
    )
    parser.add_argument("--email", required=True, help="Email of the admin user.")
    parser.add_argument(
        "--name", help="First name (required only when creating a new user)."
    )
    parser.add_argument(
        "--last-name",
        dest="last_name",
        help="Last name (required only when creating a new user).",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Prompt for the password instead of reading ADMIN_PASSWORD from the env.",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Dotenv file to read ADMIN_PASSWORD from (non-interactive mode).",
    )
    return parser.parse_args(argv)


def resolve_password(is_interactive: bool, env_file: str) -> str | None:
    if is_interactive:
        return getpass.getpass("Password: ", echo_char="*") or None
    load_dotenv(env_file)
    return os.environ.get("ADMIN_PASSWORD") or None


async def run(
    *,
    email: str,
    first_name: str | None,
    last_name: str | None,
    password_hash: str | None,
) -> tuple[str, bool]:
    # The CLI owns the transaction boundary (ADR-018): repositories never commit.
    async_session = get_sessionmaker()
    async with async_session() as session:
        user, created = await create_or_promote_admin(
            session,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password_hash=password_hash,
        )
        await session.commit()
        return user.email, created


def main() -> None:
    args = parse_args()

    password = resolve_password(args.interactive, args.env_file)

    try:
        password_hash = None
        if password is not None:
            validate_password(password)
            password_hash = hash_password(password)
        email, created = asyncio.run(
            run(
                email=args.email,
                first_name=args.name,
                last_name=args.last_name,
                password_hash=password_hash,
            )
        )
    except ValueError as exc:
        # Bad password length, or creating a new admin without --name/--last-name.
        raise SystemExit(f"error: {exc}") from exc
    except IntegrityError as exc:
        raise SystemExit(
            "error: could not create the user — the email may already be in use "
            "(possibly by a soft-deleted account)."
        ) from exc

    if created:
        print(f"Created admin user: {email}")
    else:
        print(f"Promoted existing user to admin (password unchanged): {email}")


if __name__ == "__main__":
    main()
