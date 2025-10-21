from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate password hash"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    from ..config.settings import settings
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def verify_token(token: str) -> Optional[str]:
    """Verify JWT token and return user email"""
    from ..config.settings import settings
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        if not payload:
            return None
        email: str = payload.get("sub")
        if not email:
            return None
        return email
    except JWTError:
        return None


def authenticate_user(db_session, email: str, password: str):
    """Authenticate user with email and password using Neo4j"""
    result = db_session.run("""
        MATCH (u:User {email: $email})
        RETURN u
    """, email=email)

    user_record = result.single()
    if not user_record:
        return None

    user_data = user_record["u"]
    if not verify_password(password, user_data.get("hashed_password", "")):
        return None

    # Convert Neo4j node properties to a simple dict
    return dict(user_data)


def get_current_user_from_token(token: str, db_session, secret_key: str = "", algorithm: str = "HS256"):
    """Get current user from JWT token using Neo4j"""
    email = verify_token(token, secret_key, algorithm)
    if email is None:
        return None

    result = db_session.run("""
        MATCH (u:User {email: $email})
        RETURN u
    """, email=email)

    user_record = result.single()
    if not user_record:
        return None

    return dict(user_record["u"])
