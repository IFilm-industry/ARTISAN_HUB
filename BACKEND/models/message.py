from pydantic import BaseModel

class MessageCreate(BaseModel):
    conversationId: str
    encryptedContent: str
    iv: str
