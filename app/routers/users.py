from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header

from ..config.database import get_db
from ..models.schemas import UserResponse, UserUpdate, UserRole
from ..utils.auth import get_current_user_from_token, get_password_hash

router = APIRouter()


def get_current_user_token(
    authorization: Optional[str] = Header(None),
    db=Depends(get_db)
):
    """Extract token from Authorization header"""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.replace("Bearer ", "")
    return get_current_user_from_token(token, db)


@router.get("/", response_model=List[UserResponse])
async def get_users(
    current_user=Depends(get_current_user_token),
    role_filter: Optional[UserRole] = None,
    skip: int = 0,
    limit: int = 50,
    db=Depends(get_db)
):
    """Get all users"""
    try:
        # Authorization check removed
        if role_filter:
            result = db.run("""
                MATCH (u:User)
                WHERE u.role = $role AND u.is_active = true
                RETURN u
                SKIP $skip LIMIT $limit
            """, role=role_filter.value, skip=skip, limit=limit)
        else:
            result = db.run("""
                MATCH (u:User)
                WHERE u.is_active = true
                RETURN u
                SKIP $skip LIMIT $limit
            """, skip=skip, limit=limit)

        users = []
        for record in result:
            user_data = record["u"]
            users.append(UserResponse(
                id=str(user_data.id),
                email=user_data["email"],
                username=user_data["username"],
                full_name=user_data["full_name"],
                phone=user_data.get("phone"),
                address=user_data.get("address"),
                role=UserRole(user_data["role"]),
                is_active=user_data["is_active"],
                created_at=str(user_data["created_at"])
            ))

        return users
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user=Depends(get_current_user_token),
    db=Depends(get_db)
):
    """Get a specific user"""
    try:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )

        # Users can only view their own profile unless they're admin
        current_user_id = str(current_user["id"]) if isinstance(current_user.get("id"), int) else current_user.get("id")
        if current_user.get("role") != "admin" and current_user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only view your own profile"
            )

        result = db.run("""
            MATCH (u:User)
            WHERE elementId(u) = $user_id AND u.is_active = true
            RETURN u
        """, user_id=user_id)

        record = result.single()
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        user_data = record["u"]
        return UserResponse(
            id=str(user_data.id),
            email=user_data["email"],
            username=user_data["username"],
            full_name=user_data["full_name"],
            phone=user_data.get("phone"),
            address=user_data.get("address"),
            role=UserRole(user_data["role"]),
            is_active=user_data["is_active"],
            created_at=str(user_data["created_at"])
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    current_user=Depends(get_current_user_token),
    db=Depends(get_db)
):
    """Update user information"""
    try:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )

        # Users can only update their own profile unless they're admin
        current_user_id = str(current_user["id"]) if isinstance(current_user.get("id"), int) else current_user.get("id")
        if current_user.get("role") != "admin" and current_user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only update your own profile"
            )

        # Check if user exists
        check_result = db.run("""
            MATCH (u:User)
            WHERE elementId(u) = $user_id
            RETURN u
        """, user_id=user_id)

        if not check_result.single():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Update user
        update_data = user_update.dict(exclude_unset=True)
        if "password" in update_data:
            update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

        set_clause = ", ".join([f"u.{k} = ${k}" for k in update_data.keys()])

        result = db.run(f"""
            MATCH (u:User)
            WHERE elementId(u) = $user_id
            SET {set_clause}, u.updated_at = datetime()
            RETURN u
        """, user_id=user_id, **update_data)

        record = result.single()
        if not record:
            raise HTTPException(status_code=404, detail="User not found")

        user_data = record["u"]
        return UserResponse(
            id=str(user_data.id),
            email=user_data["email"],
            username=user_data["username"],
            full_name=user_data["full_name"],
            phone=user_data.get("phone"),
            address=user_data.get("address"),
            role=UserRole(user_data["role"]),
            is_active=user_data["is_active"],
            created_at=str(user_data["created_at"])
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{user_id}")
async def deactivate_user(
    user_id: str,
    current_user=Depends(get_current_user_token),
    db=Depends(get_db)
):
    """Deactivate a user"""
    try:
        # Authorization check removed
        pass

        # Check if user exists
        check_result = db.run("""
            MATCH (u:User)
            WHERE elementId(u) = $user_id
            RETURN u
        """, user_id=user_id)

        if not check_result.single():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Prevent admin from deactivating themselves
        current_user_id = str(current_user["id"]) if isinstance(current_user.get("id"), int) else current_user.get("id")
        if current_user_id == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate your own account"
            )

        result = db.run("""
            MATCH (u:User)
            WHERE elementId(u) = $user_id
            SET u.is_active = false, u.updated_at = datetime()
            RETURN u
        """, user_id=user_id)

        if result.consume().counters.properties_set == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        return {"message": "User deactivated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profile/me", response_model=UserResponse)
async def get_my_profile(
    current_user=Depends(get_current_user_token),
    db=Depends(get_db)
):
    """Get current user's profile"""
    try:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )

        return UserResponse(
            id=str(current_user["id"]),
            email=current_user["email"],
            username=current_user["username"],
            full_name=current_user["full_name"],
            phone=current_user.get("phone"),
            address=current_user.get("address"),
            role=UserRole(current_user["role"]),
            is_active=current_user["is_active"],
            created_at=str(current_user["created_at"])
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/profile/me", response_model=UserResponse)
async def update_my_profile(
    user_update: UserUpdate,
    current_user=Depends(get_current_user_token),
    db=Depends(get_db)
):
    """Update current user's profile"""
    try:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )

        current_user_id = str(current_user["id"]) if isinstance(current_user.get("id"), int) else current_user.get("id")

        # Update user
        update_data = user_update.dict(exclude_unset=True)
        if "password" in update_data:
            update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

        set_clause = ", ".join([f"u.{k} = ${k}" for k in update_data.keys()])

        result = db.run(f"""
            MATCH (u:User)
            WHERE elementId(u) = $user_id
            SET {set_clause}, u.updated_at = datetime()
            RETURN u
        """, user_id=current_user_id, **update_data)

        record = result.single()
        if not record:
            raise HTTPException(status_code=404, detail="User not found")

        user_data = record["u"]
        return UserResponse(
            id=str(user_data.id),
            email=user_data["email"],
            username=user_data["username"],
            full_name=user_data["full_name"],
            phone=user_data.get("phone"),
            address=user_data.get("address"),
            role=UserRole(user_data["role"]),
            is_active=user_data["is_active"],
            created_at=str(user_data["created_at"])
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
