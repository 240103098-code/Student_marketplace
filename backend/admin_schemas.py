"""Minimal admin user list and exact suspension input."""
from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,field_serializer

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


class AdminListingSeller(BaseModel):
 id:int
 email:str
 name:str|None

class AdminListingSummary(BaseModel):
 id:int
 title:str
 price:Decimal
 currency:Literal['KZT']
 category_id:int
 condition:Literal['new','used']
 status:Literal['pending','active','sold','rejected','removed']
 created_at:datetime
 published_at:datetime|None
 seller:AdminListingSeller
 @field_serializer('price')
 def canonical_price(self,value):return format(value,'.2f')

class AdminListingsPage(BaseModel):
 items:list[AdminListingSummary]
 total:int
 count:int
 limit:int
 offset:int
 status:Literal['pending','active','sold','rejected','removed']|None

from backend.listing_schemas import ListingPhotoSummary
class AdminListingDetail(AdminListingSummary):
 description:str
 rejection_reason:str|None
 photos:list[ListingPhotoSummary]


class AdminReportListing(BaseModel):
 id:int
 title:str
 status:Literal['pending','active','sold','rejected','removed']
 url:str

class AdminReportResponse(BaseModel):
 id:int
 reason:Literal['spam','prohibited_items','misleading_information']
 created_at:datetime
 reviewed_at:datetime|None
 listing:AdminReportListing

class AdminReportsPage(BaseModel):
 items:list[AdminReportResponse]
 total:int
 count:int
 limit:int
 offset:int
 state:Literal['unreviewed','reviewed','all']
