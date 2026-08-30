from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, ConfigDict


# ---------- Auth ----------

class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Users ----------

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    created_at: datetime


# ---------- Messages ----------

class MessageCreate(BaseModel):
    receiver_id: int
    message: str = Field(min_length=1, max_length=2000)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sender_id: int
    receiver_id: int
    message: str
    created_at: datetime


# ---------- Health ----------

class HealthOut(BaseModel):
    status: str


class ReadyOut(BaseModel):
    status: str
    database: str
