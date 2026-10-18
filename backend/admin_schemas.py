"""Minimal admin user list and exact suspension input."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field

class SuspensionRequest(BaseModel):
 model_config=ConfigDict(extra='forbid',hide_input_in_errors=True)
 suspended:bool=Field(strict=True)

class AdminUserResponse(BaseModel):
 model_config=ConfigDict(from_attributes=True)
 id:int
 email:str
 name:str|None
 role:Literal['student','admin']
 verified:bool
 suspended:bool
 created_at:datetime

class AdminUsersPage(BaseModel):
 items:list[AdminUserResponse]
 total:int
 count:int
 limit:int
 offset:int
