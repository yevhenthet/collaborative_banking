import bcrypt
from fastapi import Request, HTTPException
from sqlalchemy.orm import Session
from . import models


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def get_current_user(request: Request, db: Session) -> models.User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return user


def require_admin(request: Request, db: Session) -> models.User:
    user = get_current_user(request, db)
    if user.role != models.Role.admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
