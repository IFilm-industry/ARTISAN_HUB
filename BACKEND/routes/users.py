import re
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends
from bson import ObjectId
from BACKEND.config.db import get_db
from BACKEND.middleware.auth import protect
from BACKEND.models.user import UserProfileUpdate
from BACKEND.models.utils import serialize_doc

router = APIRouter()

# GET /api/users
@router.get("/")
async def get_users(
    request: Request,
    search: str = None,
    role: str = None,
    skill: str = None,
    page: int = 1,
    limit: int = 20
):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected")
        
    query = {}
    
    # Text search across name, bio, and skills
    if search:
        search_regex = {"$regex": search, "$options": "i"}
        query["$or"] = [
            {"name": search_regex},
            {"bio": search_regex},
            {"skills": search_regex}
        ]
        
    if role:
        query["role"] = role
        
    if skill:
        # Matches if the skill regex is in the skills array
        query["skills"] = {"$regex": skill, "$options": "i"}
        
    skip = (page - 1) * limit
    
    users_cursor = db.users.find(query, {"password": 0}).sort("createdAt", -1).skip(skip).limit(limit)
    users = await users_cursor.to_list(length=limit)
    
    total = await db.users.count_documents(query)
    pages = (total + limit - 1) // limit if limit > 0 else 0
    
    return {
        "users": serialize_doc(users),
        "page": page,
        "pages": pages,
        "total": total
    }

# GET /api/users/:id
@router.get("/{id}")
async def get_user_by_id(id: str):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected")
        
    try:
        user_oid = ObjectId(id)
    except Exception:
        raise HTTPException(status_code=404, detail={"message": "User not found"})
        
    user = await db.users.find_one({"_id": user_oid}, {"password": 0})
    if not user:
        raise HTTPException(status_code=404, detail={"message": "User not found"})
        
    return serialize_doc(user)

# PUT /api/users/profile
@router.put("/profile")
async def update_profile(request: Request, payload: UserProfileUpdate, user: dict = Depends(protect)):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected")
        
    user_id = ObjectId(user["_id"])
    
    update_data = {}
    if payload.name is not None:
        update_data["name"] = payload.name
        
    if payload.bio is not None:
        update_data["bio"] = payload.bio
        
    if payload.skills is not None:
        if isinstance(payload.skills, list):
            update_data["skills"] = payload.skills
        elif isinstance(payload.skills, str):
            update_data["skills"] = [s.strip() for s in payload.skills.split(",") if s.strip()]
        else:
            update_data["skills"] = []
            
    if payload.location is not None:
        update_data["location"] = payload.location
        
    if payload.website is not None:
        update_data["website"] = payload.website
        
    if payload.socialLinks is not None:
        # Merge or set socialLinks
        update_data["socialLinks"] = {
            "instagram": payload.socialLinks.instagram or "",
            "youtube": payload.socialLinks.youtube or "",
            "twitter": payload.socialLinks.twitter or ""
        }
        
    if payload.avatar is not None:
        update_data["avatar"] = payload.avatar
        
    if payload.banner is not None:
        update_data["banner"] = payload.banner
        
    if payload.publicKey is not None:
        update_data["publicKey"] = payload.publicKey
        
    if update_data:
        update_data["updatedAt"] = datetime.utcnow()
        await db.users.update_one({"_id": user_id}, {"$set": update_data})
        
    # Get updated user
    updated_user = await db.users.find_one({"_id": user_id})
    
    return {
        "_id": str(updated_user["_id"]),
        "name": updated_user.get("name", ""),
        "email": updated_user.get("email", ""),
        "role": updated_user.get("role", "artist"),
        "isVerified": updated_user.get("isVerified", False),
        "avatar": updated_user.get("avatar", ""),
        "bio": updated_user.get("bio", ""),
        "skills": updated_user.get("skills", []),
        "location": updated_user.get("location", "")
    }

# PUT /api/users/:id/follow
@router.put("/{id}/follow")
async def follow_unfollow_user(request: Request, id: str, user: dict = Depends(protect)):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected")
        
    current_user_id = str(user["_id"])
    if id == current_user_id:
        raise HTTPException(status_code=400, detail={"message": "You cannot follow yourself"})
        
    try:
        target_user_oid = ObjectId(id)
    except Exception:
        raise HTTPException(status_code=404, detail={"message": "User not found"})
        
    target_user = await db.users.find_one({"_id": target_user_oid})
    if not target_user:
        raise HTTPException(status_code=404, detail={"message": "User not found"})
        
    current_user_oid = ObjectId(current_user_id)
    
    # Mongoose uses Array of ObjectIds. Let's make sure we query or cast properly.
    # Convert followers/following list to strings for easy membership testing
    current_following = [str(fid) for fid in user.get("following", [])]
    
    is_following = id in current_following
    
    if is_following:
        # Unfollow
        await db.users.update_one({"_id": current_user_oid}, {"$pull": {"following": target_user_oid}})
        await db.users.update_one({"_id": target_user_oid}, {"$pull": {"followers": current_user_oid}})
    else:
        # Follow
        await db.users.update_one({"_id": current_user_oid}, {"$addToSet": {"following": target_user_oid}})
        await db.users.update_one({"_id": target_user_oid}, {"$addToSet": {"followers": current_user_oid}})
        
    return {"following": not is_following}
