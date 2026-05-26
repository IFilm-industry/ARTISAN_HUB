from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional

class SocialLinks(BaseModel):
    instagram: str = ""
    youtube: str = ""
    twitter: str = ""

class UserSignUp(BaseModel):
    name: str
    email: str
    password: str
    role: str = "artist"
    companyRegNumber: str = ""
    publicKey: str = ""

class UserLogin(BaseModel):
    email: str
    password: str

class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    bio: Optional[str] = None
    skills: Optional[list] = None  # can be list of str or string to split
    location: Optional[str] = None
    website: Optional[str] = None
    socialLinks: Optional[SocialLinks] = None
    avatar: Optional[str] = None
    banner: Optional[str] = None
    publicKey: Optional[str] = None
