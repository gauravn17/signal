from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException
from sqlmodel import Session

from signal_backend.db.session import engine
from signal_backend.models import UserRole
from signal_backend.services import auth


def _request(token: str | None) -> SimpleNamespace:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return SimpleNamespace(headers=headers)


def test_missing_auth_header_raises_401():
    with Session(engine, expire_on_commit=False) as session:
        with pytest.raises(HTTPException) as exc_info:
            auth.get_current_user(_request(None), session)
    assert exc_info.value.status_code == 401


def test_invalid_token_raises_401(monkeypatch):
    def _raise(token):
        raise jwt.InvalidTokenError("bad signature")

    monkeypatch.setattr(auth, "verify_token", _raise)
    with Session(engine, expire_on_commit=False) as session:
        with pytest.raises(HTTPException) as exc_info:
            auth.get_current_user(_request("badtoken"), session)
    assert exc_info.value.status_code == 401


def test_token_without_email_claim_raises_401(monkeypatch):
    monkeypatch.setattr(auth, "verify_token", lambda token: {"sub": f"clerk_{uuid4()}"})
    with Session(engine, expire_on_commit=False) as session:
        with pytest.raises(HTTPException) as exc_info:
            auth.get_current_user(_request("sometoken"), session)
    assert exc_info.value.status_code == 401


def test_provisions_new_user_on_first_login(monkeypatch):
    external_id = f"clerk_{uuid4()}"
    email = f"new-{uuid4()}@example.com"
    monkeypatch.setattr(auth, "verify_token", lambda token: {"sub": external_id, "email": email})

    with Session(engine, expire_on_commit=False) as session:
        user = auth.get_current_user(_request("sometoken"), session)

    assert user.email == email
    assert user.role == UserRole.admin
    assert user.organization_id is not None


def test_returns_existing_user_without_reprovisioning(monkeypatch):
    external_id = f"clerk_{uuid4()}"
    email = f"existing-{uuid4()}@example.com"
    monkeypatch.setattr(auth, "verify_token", lambda token: {"sub": external_id, "email": email})

    with Session(engine, expire_on_commit=False) as session:
        first = auth.get_current_user(_request("t1"), session)
    with Session(engine, expire_on_commit=False) as session:
        second = auth.get_current_user(_request("t2"), session)

    assert first.id == second.id
    assert first.organization_id == second.organization_id
