import os
import time
import random
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Depends, File, UploadFile, Form
from bson import ObjectId
from BACKEND.config.db import get_db
from BACKEND.middleware.auth import protect
from BACKEND.models.utils import serialize_doc

router = APIRouter()

# Ensure uploads directory exists
os.makedirs("BACKEND/uploads", exist_ok=True)

# Helper function to manually populate author and comment users
async def populate_author_and_comments(db, posts):
    if not posts:
        return posts
        
    is_list = isinstance(posts, list)
    posts_list = posts if is_list else [posts]
    
    author_ids = set()
    comment_user_ids = set()
    
    for post in posts_list:
        if "author" in post and post["author"]:
            try:
                author_ids.add(ObjectId(post["author"]))
            except Exception:
                pass
        for comment in post.get("comments", []):
            if "user" in comment and comment["user"]:
                try:
                    comment_user_ids.add(ObjectId(comment["user"]))
                except Exception:
                    pass
                
    authors_map = {}
    if author_ids:
        authors = await db.users.find(
            {"_id": {"$in": list(author_ids)}},
            {"name": 1, "avatar": 1, "role": 1, "isVerified": 1}
        ).to_list(length=len(author_ids))
        authors_map = {str(u["_id"]): u for u in authors}
        
    comment_users_map = {}
    if comment_user_ids:
        comment_users = await db.users.find(
            {"_id": {"$in": list(comment_user_ids)}},
            {"name": 1, "avatar": 1}
        ).to_list(length=len(comment_user_ids))
        comment_users_map = {str(u["_id"]): u for u in comment_users}
        
    for post in posts_list:
        auth_id_str = str(post.get("author", ""))
        if auth_id_str in authors_map:
            author_info = authors_map[auth_id_str]
            post["author"] = {
                "_id": str(author_info["_id"]),
                "name": author_info.get("name", ""),
                "avatar": author_info.get("avatar", ""),
                "role": author_info.get("role", "artist"),
                "isVerified": author_info.get("isVerified", False)
            }
        else:
            post["author"] = None
            
        for comment in post.get("comments", []):
            c_user_id_str = str(comment.get("user", ""))
            if c_user_id_str in comment_users_map:
                c_user_info = comment_users_map[c_user_id_str]
                comment["user"] = {
                    "_id": str(c_user_info["_id"]),
                    "name": c_user_info.get("name", ""),
                    "avatar": c_user_info.get("avatar", "")
                }
            else:
                comment["user"] = None
                
    return posts_list if is_list else posts_list[0]

# POST /api/posts
@router.post("/", status_code=201)
async def create_post(
    request: Request,
    type: Optional[str] = Form(None),
    content: Optional[str] = Form(""),
    tags: Optional[str] = Form(""),
    media: Optional[UploadFile] = File(None),
    user: dict = Depends(protect)
):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected")
        
    post_type = type or "text"
    parsed_tags = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    
    post_data = {
        "author": ObjectId(user["_id"]),
        "type": post_type,
        "content": content or "",
        "mediaUrl": "",
        "likes": [],
        "comments": [],
        "tags": parsed_tags,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    }
    
    if media:
        allowed_extensions = {".jpeg", ".jpg", ".png", ".gif", ".webp", ".mp4", ".webm", ".mov", ".avi"}
        ext = os.path.splitext(media.filename)[1].lower()
        
        # Verify extension or mimetype matches
        if ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail={"message": "Only image and video files are allowed"}
            )
            
        unique_suffix = f"{int(time.time() * 1000)}-{random.randint(1, 1000000000)}"
        filename = f"{unique_suffix}{ext}"
        filepath = os.path.join("BACKEND", "uploads", filename)
        
        try:
            with open(filepath, "wb") as buffer:
                # Read and save file content
                content_bytes = await media.read()
                buffer.write(content_bytes)
            post_data["mediaUrl"] = f"/uploads/{filename}"
        except Exception as e:
            raise HTTPException(status_code=500, detail={"message": f"File save failed: {str(e)}"})
            
    result = await db.posts.insert_one(post_data)
    post_id = result.inserted_id
    
    # Retrieve and populate
    created_post = await db.posts.find_one({"_id": post_id})
    populated_post = await populate_author_and_comments(db, created_post)
    
    return serialize_doc(populated_post)

# GET /api/posts (paginated)
@router.get("/")
async def get_posts(request: Request, page: int = 1, limit: int = 20):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected")
        
    skip = (page - 1) * limit
    
    posts_cursor = db.posts.find().sort("createdAt", -1).skip(skip).limit(limit)
    posts = await posts_cursor.to_list(length=limit)
    
    # Populate author and comment users
    populated_posts = await populate_author_and_comments(db, posts)
    
    total = await db.posts.count_documents({})
    pages = (total + limit - 1) // limit if limit > 0 else 0
    
    return {
        "posts": serialize_doc(populated_posts),
        "page": page,
        "pages": pages,
        "total": total
    }

# GET /api/posts/user/:userId
@router.get("/user/{userId}")
async def get_user_posts(userId: str):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected")
        
    try:
        author_oid = ObjectId(userId)
    except Exception:
        raise HTTPException(status_code=400, detail={"message": "Invalid user ID"})
        
    posts_cursor = db.posts.find({"author": author_oid}).sort("createdAt", -1)
    posts = await posts_cursor.to_list(length=1000)
    
    populated_posts = await populate_author_and_comments(db, posts)
    
    return serialize_doc(populated_posts)

# PUT /api/posts/:id/like (toggle)
@router.put("/{id}/like")
async def toggle_like(id: str, user: dict = Depends(protect)):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected")
        
    try:
        post_oid = ObjectId(id)
    except Exception:
        raise HTTPException(status_code=404, detail={"message": "Post not found"})
        
    post = await db.posts.find_one({"_id": post_oid})
    if not post:
        raise HTTPException(status_code=404, detail={"message": "Post not found"})
        
    current_user_oid = ObjectId(user["_id"])
    likes = post.get("likes", [])
    
    # Convert all elements in likes to ObjectId to ensure exact match
    likes_oids = []
    for l in likes:
        try:
            likes_oids.append(ObjectId(l))
        except Exception:
            pass
            
    if current_user_oid in likes_oids:
        # Pull like
        await db.posts.update_one({"_id": post_oid}, {"$pull": {"likes": current_user_oid}})
        likes_oids.remove(current_user_oid)
    else:
        # Push like
        await db.posts.update_one({"_id": post_oid}, {"$addToSet": {"likes": current_user_oid}})
        likes_oids.append(current_user_oid)
        
    # Return string representations of ObjectIds
    return {"likes": [str(l) for l in likes_oids]}

# POST /api/posts/:id/comment
@router.post("/{id}/comment")
async def add_comment(request: Request, id: str, comment_payload: dict, user: dict = Depends(protect)):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected")
        
    try:
        post_oid = ObjectId(id)
    except Exception:
        raise HTTPException(status_code=404, detail={"message": "Post not found"})
        
    post = await db.posts.find_one({"_id": post_oid})
    if not post:
        raise HTTPException(status_code=404, detail={"message": "Post not found"})
        
    text = comment_payload.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail={"message": "Comment text is required"})
        
    comment_oid = ObjectId()
    new_comment = {
        "_id": comment_oid,
        "user": ObjectId(user["_id"]),
        "text": text,
        "createdAt": datetime.utcnow()
    }
    
    await db.posts.update_one({"_id": post_oid}, {"$push": {"comments": new_comment}})
    
    # Fetch updated post and populate
    updated_post = await db.posts.find_one({"_id": post_oid})
    populated_post = await populate_author_and_comments(db, updated_post)
    
    return serialize_doc(populated_post["comments"])
