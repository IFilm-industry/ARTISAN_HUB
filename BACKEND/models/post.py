from pydantic import BaseModel
from typing import Optional, List

class CommentCreate(BaseModel):
    text: str
