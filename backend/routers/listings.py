"""Listing submission and fixed categories; no browsing/photo routes."""

import json
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError

from backend.authentication import AuthenticationError, authentication_required, require_verified_user
from backend.listing_schemas import ListingCreateRequest, OwnListingResponse
from backend.listings import SellerContactRequired, create_own_listing, fixed_categories

router=APIRouter(tags=['listing submission'])


def unique_fields(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate field')
        result[key]=value
    return result


def reject_constant(value):raise ValueError('Nonfinite JSON value')


async def exact_listing_payload(request:Request):
    if request.headers.get('content-type','').split(';',1)[0].strip().lower() != 'application/json':
        raise HTTPException(status_code=422,detail='Invalid listing request.')
    raw=bytearray()
    async for chunk in request.stream():
        if len(raw)+len(chunk)>65536:raise HTTPException(status_code=422,detail='Invalid listing request.')
        raw.extend(chunk)
    try:
        value=json.loads(raw,parse_float=Decimal,parse_constant=reject_constant,object_pairs_hook=unique_fields)
        return ListingCreateRequest.model_validate(value)
    except (ValidationError,ValueError,TypeError,UnicodeError):
        raise HTTPException(status_code=422,detail='Invalid listing request.') from None


@router.post('/listings',status_code=201,response_model=OwnListingResponse,openapi_extra={'requestBody':{'required':True,'content':{'application/json':{'schema':ListingCreateRequest.model_json_schema()}}}})
def submit_listing(request:Request,user=Depends(require_verified_user),payload=Depends(exact_listing_payload)):
    try:
        listing=create_own_listing(request.app.state.database,user.id,
            request.headers['authorization'].split(' ',1)[1],payload,
            request.app.state.settings,clock=request.app.state.clock)
    except SellerContactRequired:
        raise HTTPException(status_code=400,detail='Add a valid contact method to your profile before creating a listing.') from None
    except AuthenticationError:
        raise authentication_required() from None
    return OwnListingResponse.model_validate(listing)


@router.get('/categories')
def categories(request:Request,user=Depends(require_verified_user)):
    return fixed_categories(request.app.state.database)
