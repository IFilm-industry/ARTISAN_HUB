from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends
from bson import ObjectId
from BACKEND.config.db import get_db
from BACKEND.middleware.auth import protect
from BACKEND.models.conversation import ConversationCreate
from BACKEND.models.message import MessageCreate
from BACKEND.models.utils import serialize_doc

router = APIRouter()

# Helper function to populate participants in conversations
async def populate_conversation_participants(db, conversations):
    if not conversations:
        return conversations
    is_list = isinstance(conversations, list)
    conv_list = conversations if is_list else [conversations]
    
    participant_ids = set()
    for conv in conv_list:
        for p in conv.get("participants", []):
            try:
                participant_ids.add(ObjectId(p))
            except Exception:
                pass
                
    participants_map = {}
    if participant_ids:
        users = await db.users.find(
            {"_id": {"$in": list(participant_ids)}},
            {"name": 1, "avatar": 1, "role": 1, "isVerified": 1}
        ).to_list(length=len(participant_ids))
        participants_map = {str(u["_id"]): u for u in users}
        
    for conv in conv_list:
        populated_parts = []
        for p in conv.get("participants", []):
            p_str = str(p)
            if p_str in participants_map:
                u_info = participants_map[p_str]
                populated_parts.append({
                    "_id": p_str,
                    "name": u_info.get("name", ""),
                    "avatar": u_info.get("avatar", ""),
                    "role": u_info.get("role", "artist"),
                    "isVerified": u_info.get("isVerified", False)
                })
        conv["participants"] = populated_parts
        
    return conv_list if is_list else conv_list[0]

# Helper function to populate message sender
async def populate_message_sender(db, messages):
    if not messages:
        return messages
    is_list = isinstance(messages, list)
    msg_list = messages if is_list else [messages]
    
    sender_ids = set()
    for msg in msg_list:
        if "sender" in msg and msg["sender"]:
            try:
                sender_ids.add(ObjectId(msg["sender"]))
            except Exception:
                pass
                
    senders_map = {}
    if sender_ids:
        users = await db.users.find(
            {"_id": {"$in": list(sender_ids)}},
            {"name": 1, "avatar": 1}
        ).to_list(length=len(sender_ids))
        senders_map = {str(u["_id"]): u for u in users}
        
    for msg in msg_list:
        s_str = str(msg.get("sender", ""))
        if s_str in senders_map:
            u_info = senders_map[s_str]
            msg["sender"] = {
                "_id": s_str,
                "name": u_info.get("name", ""),
                "avatar": u_info.get("avatar", "")
            }
        else:
            msg["sender"] = None
            
    return msg_list if is_list else msg_list[0]

# POST /api/chat/conversation
@router.post("/conversation")
async def get_or_create_conversation(request: Request, payload: ConversationCreate, user: dict = Depends(protect)):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected")
        
    current_user_oid = ObjectId(user["_id"])
    try:
        participant_oid = ObjectId(payload.participantId)
    except Exception:
        raise HTTPException(status_code=400, detail={"message": "Invalid participant ID"})
        
    # Check if conversation already exists
    # $all checks if participants array contains both current_user_oid and participant_oid
    existing_conv = await db.conversations.find_one({
        "participants": {"$all": [current_user_oid, participant_oid]}
    })
    
    if existing_conv:
        populated_conv = await populate_conversation_participants(db, existing_conv)
        return serialize_doc(populated_conv)
        
    # Create new conversation
    new_conv = {
        "participants": [current_user_oid, participant_oid],
        "lastMessage": "",
        "lastMessageAt": datetime.utcnow(),
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    }
    
    result = await db.conversations.insert_one(new_conv)
    conv_id = result.inserted_id
    
    created_conv = await db.conversations.find_one({"_id": conv_id})
    populated_conv = await populate_conversation_participants(db, created_conv)
    
    return serialize_doc(populated_conv)

# GET /api/chat/conversations
@router.get("/conversations")
async def list_conversations(request: Request, user: dict = Depends(protect)):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected")
        
    current_user_oid = ObjectId(user["_id"])
    
    conversations_cursor = db.conversations.find({
        "participants": current_user_oid
    }).sort("lastMessageAt", -1)
    
    conversations = await conversations_cursor.to_list(length=1000)
    populated_convs = await populate_conversation_participants(db, conversations)
    
    return serialize_doc(populated_convs)

# GET /api/chat/messages/:conversationId
@router.get("/messages/{conversationId}")
async def get_messages(request: Request, conversationId: str, page: int = 1, limit: int = 50, user: dict = Depends(protect)):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected")
        
    try:
        conv_oid = ObjectId(conversationId)
    except Exception:
        raise HTTPException(status_code=400, detail={"message": "Invalid conversation ID"})
        
    skip = (page - 1) * limit
    
    messages_cursor = db.messages.find({
        "conversation": conv_oid
    }).sort("createdAt", 1).skip(skip).limit(limit)
    
    messages = await messages_cursor.to_list(length=limit)
    populated_messages = await populate_message_sender(db, messages)
    
    return serialize_doc(populated_messages)

# POST /api/chat/messages
@router.post("/messages", status_code=201)
async def send_message(request: Request, payload: MessageCreate, user: dict = Depends(protect)):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected")
        
    current_user_oid = ObjectId(user["_id"])
    try:
        conv_oid = ObjectId(payload.conversationId)
    except Exception:
        raise HTTPException(status_code=400, detail={"message": "Invalid conversation ID"})
        
    # Create message document
    msg_doc = {
        "conversation": conv_oid,
        "sender": current_user_oid,
        "encryptedContent": payload.encryptedContent,
        "iv": payload.iv,
        "type": "text",
        "mediaUrl": "",
        "read": False,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    }
    
    result = await db.messages.insert_one(msg_doc)
    msg_id = result.inserted_id
    
    # Update last message in conversation
    await db.conversations.update_one(
        {"_id": conv_oid},
        {
            "$set": {
                "lastMessage": "🔒 Encrypted message",
                "lastMessageAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow()
            }
        }
    )
    
    created_msg = await db.messages.find_one({"_id": msg_id})
    populated_msg = await populate_message_sender(db, created_msg)
    
    return serialize_doc(populated_msg)
