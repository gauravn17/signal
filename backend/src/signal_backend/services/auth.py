import jwt
from fastapi import Depends, HTTPException, Request
from jwt import PyJWKClient
from sqlmodel import Session, select

from signal_backend.config import settings
from signal_backend.db.session import get_session
from signal_backend.models import Organization, User, UserRole

_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        if not settings.clerk_jwks_url:
            raise RuntimeError("CLERK_JWKS_URL is not configured.")
        _jwks_client = PyJWKClient(settings.clerk_jwks_url)
    return _jwks_client


def verify_token(token: str) -> dict:
    """Verifies a Clerk-issued JWT's signature, issuer, and expiry.

    Requires the Clerk JWT template to include an "email" custom claim
    (Clerk's default session token does not include it) — see
    https://clerk.com/docs/backend-requests/making/custom-session-token.
    """
    signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=settings.clerk_issuer,
        options={"require": ["exp", "iss", "sub"]},
    )


def _provision_user(session: Session, external_auth_id: str, email: str) -> User:
    """First login for this Clerk identity: give them their own organization
    as its admin. Joining an existing org happens via a separate invite flow
    (not yet built) rather than automatically here."""
    org = Organization(name=f"{email}'s Organization")
    session.add(org)
    session.flush()  # populate org.id without ending the transaction
    user = User(organization_id=org.id, email=email, role=UserRole.admin, external_auth_id=external_auth_id)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def get_current_user(request: Request, session: Session = Depends(get_session)) -> User:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = auth_header.removeprefix("Bearer ")

    try:
        claims = verify_token(token)
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    external_auth_id = claims["sub"]
    email = claims.get("email")

    user = session.exec(select(User).where(User.external_auth_id == external_auth_id)).first()
    if user is None:
        if not email:
            raise HTTPException(status_code=401, detail="Token missing email claim; cannot provision user")
        user = _provision_user(session, external_auth_id, email)
    return user
