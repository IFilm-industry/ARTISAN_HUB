import os
import jwt
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends, status
from bson import ObjectId
from BACKEND.config.db import get_db
from BACKEND.models.user import UserSignUp, UserLogin
from BACKEND.middleware.auth import get_password_hash, verify_password, generate_token
from BACKEND.models.utils import serialize_doc

router = APIRouter()

# POST /api/auth/signup
@router.post("/signup", status_code=201)
async def signup(payload: UserSignUp):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected")
        
    email_lower = payload.email.lower().strip()
    
    # Check user existence
    user_exists = await db.users.find_one({"email": email_lower})
    if user_exists:
        raise HTTPException(
            status_code=400,
            detail={"message": "User already exists with this email"}
        )
        
    # Set verification based on role
    is_verified = True if payload.role == "production_company" else False
    
    # Prepare User document
    user_doc = {
        "name": payload.name.strip(),
        "email": email_lower,
        "password": get_password_hash(payload.password),
        "role": payload.role or "artist",
        "isVerified": is_verified,
        "avatar": "",
        "banner": "",
        "bio": "",
        "skills": [],
        "location": "",
        "companyRegNumber": payload.companyRegNumber or "",
        "publicKey": payload.publicKey or "",
        "followers": [],
        "following": [],
        "website": "",
        "socialLinks": {
            "instagram": "",
            "youtube": "",
            "twitter": ""
        },
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    }
    
    result = await db.users.insert_one(user_doc)
    user_id = result.inserted_id
    
    return {
        "_id": str(user_id),
        "name": user_doc["name"],
        "email": user_doc["email"],
        "role": user_doc["role"],
        "isVerified": user_doc["isVerified"],
        "avatar": user_doc["avatar"],
        "token": generate_token(user_id)
    }

# POST /api/auth/login
@router.post("/login")
async def login(payload: UserLogin):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected")
        
    email_lower = payload.email.lower().strip()
    user = await db.users.find_one({"email": email_lower})
    
    if user and verify_password(payload.password, user["password"]):
        return {
            "_id": str(user["_id"]),
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
            "isVerified": user["isVerified"],
            "avatar": user.get("avatar", ""),
            "bio": user.get("bio", ""),
            "token": generate_token(user["_id"])
        }
    else:
        raise HTTPException(
            status_code=401,
            detail={"message": "Invalid email or password"}
        )

# GET /api/auth/me
@router.get("/me")
async def me(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={"message": "No token"}
        )
        
    token = auth_header.split(" ")[1]
    jwt_secret = os.getenv("JWT_SECRET", "supersecretjwtkey12345!")
    
    try:
        decoded = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        user_id = decoded.get("id")
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=401,
            detail={"message": "Not authorized"}
        )
        
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected")
        
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"password": 0})
    if not user:
        raise HTTPException(
            status_code=404,
            detail={"message": "User not found"}
        )
        
    return serialize_doc(user)
