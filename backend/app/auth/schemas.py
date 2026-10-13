"""Schemas de autenticação — nunca incluem password_hash ou tokens sensíveis em /me."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Profile = Literal["ADMIN", "GESTOR", "OPERADOR", "CONSULTA"]


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=80)
    password: str = Field(..., min_length=1, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: "UserPublic"


class UserPublic(BaseModel):
    id: int
    username: str
    nome: Optional[str] = None
    perfil: Profile
    ativo: bool


class MessageResponse(BaseModel):
    detail: str
