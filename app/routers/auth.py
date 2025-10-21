from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import JWTError

from ..config.database import get_db
from ..config.settings import settings
from ..models.schemas import UserCreate, UserResponse, Token, UserLogin, UserRole
from ..utils.auth import authenticate_user, create_access_token, get_password_hash, verify_token

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


@router.post("/register", response_model=UserResponse)
async def register_user(user_data: UserCreate, db=Depends(get_db)):
    """Register a new user"""
    try:
        # Check if user already exists
        result = db.run("""
            MATCH (u:User)
            WHERE u.email = $email OR u.username = $username
            RETURN u
        """, email=user_data.email, username=user_data.username)

        existing_user = result.single()
        if existing_user:
            user = existing_user["u"]
            if user["email"] == user_data.email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken"
                )

        # Create new user
        hashed_password = get_password_hash(user_data.password)
        user_props = {
            "email": user_data.email,
            "username": user_data.username,
            "full_name": user_data.full_name,
            "phone": user_data.phone,
            "address": user_data.address,
            "hashed_password": hashed_password,
            "role": user_data.role.value,
            "is_active": True,
            "created_at": "datetime()"
        }

        result = db.run("""
            CREATE (u:User {
                email: $email,
                username: $username,
                full_name: $full_name,
                phone: $phone,
                address: $address,
                hashed_password: $hashed_password,
                role: $role,
                is_active: $is_active,
                created_at: datetime()
            })
            RETURN u
        """, **user_props)

        record = result.single()
        if not record:
            raise HTTPException(status_code=500, detail="Failed to create user")

        user_node = record["u"]

        # Return user data in the expected format
        return UserResponse(
            id=str(user_node.id),
            email=user_node["email"],
            username=user_node["username"],
            full_name=user_node["full_name"],
            phone=user_node.get("phone"),
            address=user_node.get("address"),
            role=UserRole(user_node["role"]),
            is_active=user_node["is_active"],
            created_at=str(user_node["created_at"])
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login", response_model=Token)
async def login_user(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db=Depends(get_db)
):
    """Login user and return access token"""
    try:
        user = authenticate_user(db, form_data.username, form_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.get("is_active", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )

        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": user["email"]}, expires_delta=access_token_expires
        )

        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login-form", response_model=Token)
async def login_user_form(
    user_credentials: UserLogin,
    db=Depends(get_db)
):
    """Login user with email and password (alternative endpoint)"""
    try:
        user = authenticate_user(db, user_credentials.email, user_credentials.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.get("is_active", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )

        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": user["email"]}, expires_delta=access_token_expires
        )

        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me", response_model=UserResponse)
async def get_current_user(db=Depends(get_db), token: str = Depends(oauth2_scheme)):
    """Get current user profile from token"""
    try:
        email = verify_token(token)
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        result = db.run("""
            MATCH (u:User {email: $email})
            RETURN u
        """, email=email)
        
        user_record = result.single()
        if not user_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user = user_record["u"]
        return UserResponse(
            id=str(user.id),
            email=user["email"],
            username=user["username"],
            full_name=user["full_name"],
            phone=user.get("phone"),
            address=user.get("address"),
            role=UserRole(user["role"]),
            is_active=user["is_active"],
            created_at=str(user["created_at"])
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
