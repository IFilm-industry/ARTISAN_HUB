from pydantic import BaseModel

class ConversationCreate(BaseModel):
    participantId: str
