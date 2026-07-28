from datetime import datetime, timedelta, timezone

from jose import jwt
from jose.exceptions import JWTError
from passlib.context import CryptContext

from app.config import settings

# ── Password hashing ────────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ── JWT tokens ─────────────────────────────────────────────────────────────
def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token.

    Parameters
    ----------
    data : dict
        Claims to embed in the token (must include at least ``sub``).
    expires_delta : timedelta | None
        Token lifetime.  Defaults to ``settings.ACCESS_TOKEN_EXPIRE_MINUTES``.

    Returns
    -------
    str
        Encoded JWT string.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Decode and validate a JWT access token.

    Returns the payload dict on success, or ``None`` if the token is
    expired, malformed, or otherwise invalid.
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        return None
