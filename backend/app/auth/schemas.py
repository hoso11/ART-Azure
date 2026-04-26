from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPayload(BaseModel):
    sub: str
    role: str
    exp: int


class AuthResponse(BaseModel):
    message: str
    user_id: int
    email: str
    role: str
