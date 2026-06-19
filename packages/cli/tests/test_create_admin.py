import sys

import pytest
from cli import create_admin
from sqlalchemy.exc import IntegrityError

# These tests cover the CLI module in isolation: argument parsing, password
# resolution, validation, and main()'s orchestration/messaging. The DB-touching
# create_or_promote_admin is covered against a real Postgres in the database
# package's test_user.py, so here run() is stubbed out.


# --- parse_args ---------------------------------------------------------------


def test_parse_args_minimal_defaults():
    args = create_admin.parse_args(["--email", "a@b.com"])
    assert args.email == "a@b.com"
    assert args.name is None
    assert args.last_name is None
    assert args.interactive is False
    assert args.env_file == ".env"


def test_parse_args_full():
    args = create_admin.parse_args(
        [
            "--email",
            "a@b.com",
            "--name",
            "Ada",
            "--last-name",
            "Lovelace",
            "--interactive",
            "--env-file",
            "custom.env",
        ]
    )
    assert args.name == "Ada"
    assert args.last_name == "Lovelace"
    assert args.interactive is True
    assert args.env_file == "custom.env"


def test_parse_args_email_is_required():
    with pytest.raises(SystemExit):
        create_admin.parse_args([])


# --- resolve_password ---------------------------------------------------------


def test_resolve_password_interactive(monkeypatch):
    monkeypatch.setattr(create_admin.getpass, "getpass", lambda *a, **k: "secret-pass")
    assert create_admin.resolve_password(True, ".env") == "secret-pass"


def test_resolve_password_interactive_empty_is_none(monkeypatch):
    monkeypatch.setattr(create_admin.getpass, "getpass", lambda *a, **k: "")
    assert create_admin.resolve_password(True, ".env") is None


def test_resolve_password_from_env(monkeypatch):
    # Stub load_dotenv so the test never reads a real .env file.
    monkeypatch.setattr(create_admin, "load_dotenv", lambda *a, **k: False)
    monkeypatch.setenv("ADMIN_PASSWORD", "env-pass")
    assert create_admin.resolve_password(False, ".env") == "env-pass"


def test_resolve_password_env_missing_is_none(monkeypatch):
    monkeypatch.setattr(create_admin, "load_dotenv", lambda *a, **k: False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    assert create_admin.resolve_password(False, ".env") is None


# --- main ---------------------------------------------------------------------


def _arrange_main(monkeypatch, *extra_argv, password="valid-pass"):
    argv = [
        "create-admin",
        "--email",
        "a@b.com",
        "--name",
        "Ada",
        "--last-name",
        "Lovelace",
        "--interactive",
        *extra_argv,
    ]
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(create_admin.getpass, "getpass", lambda *a, **k: password)


def test_main_reports_created(monkeypatch, capsys):
    _arrange_main(monkeypatch)

    async def fake_run(**kwargs):
        return "a@b.com", True

    monkeypatch.setattr(create_admin, "run", fake_run)

    create_admin.main()

    assert "Created admin user: a@b.com" in capsys.readouterr().out


def test_main_reports_promoted(monkeypatch, capsys):
    _arrange_main(monkeypatch)

    async def fake_run(**kwargs):
        return "a@b.com", False

    monkeypatch.setattr(create_admin, "run", fake_run)

    create_admin.main()

    assert "password unchanged" in capsys.readouterr().out


def test_main_passes_hashed_password_not_plaintext(monkeypatch):
    _arrange_main(monkeypatch, password="valid-pass")
    captured = {}

    async def fake_run(**kwargs):
        captured.update(kwargs)
        return "a@b.com", True

    monkeypatch.setattr(create_admin, "run", fake_run)

    create_admin.main()

    # run() must receive a hash, never the raw password.
    assert captured["password_hash"] != "valid-pass"
    assert captured["password_hash"].startswith("$argon2")


def test_main_value_error_exits(monkeypatch):
    _arrange_main(monkeypatch)

    async def fake_run(**kwargs):
        raise ValueError("creating a new admin requires: password_hash")

    monkeypatch.setattr(create_admin, "run", fake_run)

    with pytest.raises(SystemExit) as exc:
        create_admin.main()
    assert "password_hash" in str(exc.value)


def test_main_integrity_error_exits(monkeypatch):
    _arrange_main(monkeypatch)

    async def fake_run(**kwargs):
        raise IntegrityError("INSERT", {}, Exception("duplicate key"))

    monkeypatch.setattr(create_admin, "run", fake_run)

    with pytest.raises(SystemExit) as exc:
        create_admin.main()
    assert "email may already be in use" in str(exc.value)


def test_main_short_password_exits_before_touching_db(monkeypatch):
    _arrange_main(monkeypatch, password="short")  # below PASSWORD_MIN_LENGTH
    called = False

    async def fake_run(**kwargs):
        nonlocal called
        called = True
        return "a@b.com", True

    monkeypatch.setattr(create_admin, "run", fake_run)

    with pytest.raises(SystemExit):
        create_admin.main()
    assert called is False  # validation fails before run() is reached
