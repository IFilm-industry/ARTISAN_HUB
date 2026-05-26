import socketio
from datetime import datetime
from bson import ObjectId
from BACKEND.config.db import get_db

# Initialize Socket.IO AsyncServer
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')

# Track online users: maps user_id -> sid
online_users = {}
# Track sid -> user_id for fast disconnect lookup
sid_to_userid = {}

@sio.event
async def connect(sid, environ):
    print(f"[i] User connected: {sid}")

@sio.on("join")
async def join(sid, user_id):
    online_users[user_id] = sid
    sid_to_userid[sid] = user_id
    await sio.emit("onlineUsers", list(online_users.keys()))
    print(f"[i] User {user_id} is online")

@sio.on("joinConversation")
async def join_conversation(sid, conversation_id):
    sio.enter_room(sid, conversation_id)
    print(f"[i] Socket {sid} joined conversation room: {conversation_id}")

@sio.on("sendMessage")
async def send_message(sid, data):
    try:
        conversation_id = data.get("conversationId")
        sender_id = data.get("senderId")
        encrypted_content = data.get("encryptedContent")
        iv = data.get("iv")
        sender_name = data.get("senderName")
        sender_avatar = data.get("senderAvatar")
        
        db = get_db()
        if db is None:
            print("[ERR] Database not connected in socket_handler")
            return
            
        # Create message document
        msg_doc = {
            "conversation": ObjectId(conversation_id),
            "sender": ObjectId(sender_id),
            "encryptedContent": encrypted_content,
            "iv": iv,
            "type": "text",
            "mediaUrl": "",
            "read": False,
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow()
        }
        
        result = await db.messages.insert_one(msg_doc)
        msg_id = result.inserted_id
        
        # Update conversation lastMessage
        await db.conversations.update_one(
            {"_id": ObjectId(conversation_id)},
            {
                "$set": {
                    "lastMessage": "🔒 Encrypted message",
                    "lastMessageAt": datetime.utcnow(),
                    "updatedAt": datetime.utcnow()
                }
            }
        )
        
        # Format createdAt timestamp
        created_at_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        
        # Emit to the conversation room
        await sio.emit("newMessage", {
            "_id": str(msg_id),
            "conversation": conversation_id,
            "sender": {
                "_id": sender_id,
                "name": sender_name,
                "avatar": sender_avatar
            },
            "encryptedContent": encrypted_content,
            "iv": iv,
            "createdAt": created_at_iso
        }, room=conversation_id)
        
        print(f"[i] Message sent from {sender_name} in room {conversation_id}")
    except Exception as e:
        print("[ERR] Message socket error:", e)

@sio.on("typing")
async def typing(sid, data):
    conversation_id = data.get("conversationId")
    user_id = data.get("userId")
    name = data.get("name")
    await sio.emit("userTyping", {
        "userId": user_id,
        "name": name
    }, room=conversation_id, skip_sid=sid)

@sio.on("stopTyping")
async def stop_typing(sid, data):
    conversation_id = data.get("conversationId")
    user_id = data.get("userId")
    await sio.emit("userStopTyping", {
        "userId": user_id
    }, room=conversation_id, skip_sid=sid)

@sio.event
async def disconnect(sid):
    if sid in sid_to_userid:
        user_id = sid_to_userid[sid]
        del sid_to_userid[sid]
        if online_users.get(user_id) == sid:
            del online_users[user_id]
        await sio.emit("onlineUsers", list(online_users.keys()))
        print(f"[i] User disconnected: {sid} (User {user_id})")
    else:
        print(f"[i] User disconnected: {sid}")
