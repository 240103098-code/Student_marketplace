"""Strict listing creation with exact decimal validation before PostgreSQL."""

from datetime import datetime
from decimal import Decimal, InvalidOperation
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator


class ListingCreateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)

    title: str = Field(strict=True,min_length=3,max_length=120)
    description: str = Field(strict=True,min_length=10,max_length=2000)
    price: Decimal
    category_id: int = Field(strict=True,ge=1,le=5)
    condition: Literal['new','used']

    @field_validator('title','description',mode='before')
    @classmethod
    def trimmed_text(cls,value):
        if not isinstance(value,str) or '\x00' in value:raise ValueError('Text must be a valid string')
        return value.strip()

    @field_validator('condition',mode='before')
    @classmethod
    def strict_condition(cls,value):
        if not isinstance(value,str):raise ValueError('Condition must be a string')
        return value

    @field_validator('price',mode='before')
    @classmethod
    def exact_price(cls,value):
        if isinstance(value,bool) or not isinstance(value,(int,Decimal,str)):
            raise ValueError('Price must be an exact decimal')
        if isinstance(value,str) and not re.fullmatch(r'(?:0|[1-9][0-9]*)(?:\.[0-9]+)?',value):
            raise ValueError('Price string must use decimal syntax')
        try:
            amount=Decimal(value)
            if not amount.is_finite() or amount < 0 or amount > Decimal('1000000000'):
                raise ValueError('Price is outside the allowed range')
            _,digits,exponent=amount.as_tuple()
            trailing=0
            for digit in reversed(digits):
                if digit != 0:break
                trailing+=1
            if amount != 0 and max(0,-exponent-trailing)>2:
                raise ValueError('Price has excess fractional precision')
            return Decimal('0.00') if amount == 0 else amount.quantize(Decimal('0.01'))
        except (InvalidOperation,ValueError,OverflowError):
            raise ValueError('Price is invalid') from None


class OwnListingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:int
    title:str
    description:str
    price:Decimal
    currency:Literal['KZT']
    category_id:int
    condition:Literal['new','used']
    status:Literal['pending']
    created_at:datetime
    published_at:None

    @field_serializer('price')
    def canonical_price(self,value):return format(value,'.2f')


class ListingEditRequest(BaseModel):
    model_config = ConfigDict(extra='forbid',hide_input_in_errors=True)
    price:Decimal|None=None
    description:str|None=Field(default=None,strict=True,min_length=10,max_length=2000)

    @field_validator('price',mode='before')
    @classmethod
    def price_exact(cls,value):return ListingCreateRequest.exact_price(value)

    @field_validator('description',mode='before')
    @classmethod
    def description_trimmed(cls,value):return ListingCreateRequest.trimmed_text(value)

    @model_validator(mode='after')
    def nonempty(self):
        if not self.model_fields_set:raise ValueError('Provide price or description')
        return self


class ListingEditResponse(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:int
    title:str
    price:Decimal
    description:str
    status:Literal['pending','active','sold','rejected','removed']
    published_at:datetime|None

    @field_serializer('price')
    def canonical_price(self,value):return format(value,'.2f')


class ListingPhotoSummary(BaseModel):
    id:int
    position:int
    is_main:bool
    url:str


class MineListingResponse(OwnListingResponse):
    status:Literal['pending','active','sold','rejected','removed']
    published_at:datetime|None
    rejection_reason:str|None
    photos:list[ListingPhotoSummary]


class MineListingsPage(BaseModel):
    items:list[MineListingResponse]
    total:int
    count:int
    limit:int
    offset:int
    status:Literal['pending','active','sold','rejected','removed']|None


class BrowseListingResponse(BaseModel):
    id:int
    title:str
    price:Decimal
    currency:Literal['KZT']
    category_id:int
    condition:Literal['new','used']
    published_at:datetime
    main_photo:ListingPhotoSummary|None

    @field_serializer('price')
    def canonical_price(self,value):return format(value,'.2f')


class BrowseListingsPage(BaseModel):
    items:list[BrowseListingResponse]
    total:int
    count:int
    limit:int
    offset:int
