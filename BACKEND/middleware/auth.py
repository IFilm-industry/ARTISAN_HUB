import os
import jwt
import bcrypt
from datetime import datetime, timedelta, timezone
from fastapi import Request, HTTPException, Depends
from bson import ObjectId
from BACKEND.config.db import get_db

def truncate_password(password: str) -> bytes:
    # Node's bcryptjs silently truncates password to 72 bytes.
    # By manually truncating here to 72 bytes, we match Node's behavior exactly and avoid library exceptions.
    encoded = password.encode('utf-8')
    if len(encoded) > 72:
        return encoded[:72]
    return encoded

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        truncated_bytes = truncate_password(plain_password)
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(truncated_bytes, hashed_bytes)
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    truncated_bytes = truncate_password(password)
    # salt rounds 12 matches Mongoose default genSalt(12)
    salt = bcrypt.gensalt(rounds=12)
    hashed_bytes = bcrypt.hashpw(truncated_bytes, salt)
    return hashed_bytes.decode('utf-8')

def generate_token(user_id: str) -> str:
    jwt_secret = os.getenv("JWT_SECRET", "supersecretjwtkey12345!")
    payload = {
        "id": str(user_id),
        "exp": datetime.utcnow() + timedelta(days=30)
    }
    return jwt.encode(payload, jwt_secret, algorithm="HS256")

async def protect(request: Request):
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={"message": "Not authorized, no token"}
        )
    
    token = auth_header.split(" ")[1]
    jwt_secret = os.getenv("JWT_SECRET", "supersecretjwtkey12345!")
    
    try:
        decoded = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        user_id = decoded.get("id")
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail={"message": "Not authorized, token failed"}
            )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=401,
            detail={"message": "Not authorized, token failed"}
        )
        
    db = get_db()
    if db is None:
        raise HTTPException(
            status_code=500,
            detail={"message": "Database not connected"}
        )
        
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"password": 0})
    if not user:
        raise HTTPException(
            status_code=401,
            detail={"message": "Not authorized, token failed"}
        )
        
    request.state.user = user
    return user
