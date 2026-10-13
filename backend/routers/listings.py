"""Listing submission and fixed categories; no browsing/photo routes."""

import json
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Path
from pydantic import ValidationError

from backend.authentication import AuthenticationError, authentication_required, require_verified_user
from backend.listing_schemas import ListingCreateRequest, OwnListingResponse, ListingEditRequest, ListingEditResponse, MineListingsPage
from backend.listings import SellerContactRequired, create_own_listing, fixed_categories, ListingUnavailable, ListingEditForbidden, read_own_listing_edit, update_own_listing, own_listings_page, mark_own_listing_sold, ListingSoldForbidden, delete_own_listing

router=APIRouter(tags=['listing submission'])


def unique_fields(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate field')
        result[key]=value
    return result


def reject_constant(value):raise ValueError('Nonfinite JSON value')


async def read_exact_listing_payload(request,model,error_detail):
    if request.headers.get('content-type','').split(';',1)[0].strip().lower() != 'application/json':
        raise HTTPException(status_code=422,detail=error_detail)
    raw=bytearray()
    async for chunk in request.stream():
        if len(raw)+len(chunk)>65536:raise HTTPException(status_code=422,detail=error_detail)
        raw.extend(chunk)
    try:
        value=json.loads(raw,parse_float=Decimal,parse_constant=reject_constant,object_pairs_hook=unique_fields)
        return model.model_validate(value)
    except (ValidationError,ValueError,TypeError,UnicodeError):
        raise HTTPException(status_code=422,detail=error_detail) from None


async def exact_listing_payload(request:Request):
    return await read_exact_listing_payload(request,ListingCreateRequest,'Invalid listing request.')


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


def mine_query(request:Request):
    values={}
    try:
        for key,value in request.query_params.multi_items():
            if key not in {'limit','offset','status'} or key in values:raise ValueError()
            values[key]=value
        import re
        for key in ['limit','offset']:
            if key in values and not re.fullmatch(r'(?:0|[1-9][0-9]*)',values[key]):raise ValueError()
        limit=int(values.get('limit','20'));offset=int(values.get('offset','0'))
        status=values.get('status')
        if not 1<=limit<=50 or not 0<=offset<=9223372036854775807 or (status is not None and status not in {'pending','active','sold','rejected','removed'}):raise ValueError()
        return {'limit':limit,'offset':offset,'status':status}
    except (ValueError,OverflowError):
        raise HTTPException(status_code=422,detail='Invalid My Listings query.') from None


@router.get('/listings/mine',response_model=MineListingsPage)
def my_listings(request:Request,user=Depends(require_verified_user),query=Depends(mine_query)):
    try:
        return own_listings_page(request.app.state.database,user.id,
            request.headers['authorization'].split(' ',1)[1],request.app.state.settings,
            **query,clock=request.app.state.clock)
    except AuthenticationError:raise authentication_required() from None


async def exact_edit_payload(request:Request):
    return await read_exact_listing_payload(request,ListingEditRequest,'Invalid listing-edit request.')


@router.get('/listings/{listing_id}/edit',response_model=ListingEditResponse)
def own_edit(listing_id:Annotated[int,Path(ge=1,le=9223372036854775807)],request:Request,user=Depends(require_verified_user)):
    try:
        listing=read_own_listing_edit(request.app.state.database,user.id,
            request.headers['authorization'].split(' ',1)[1],listing_id,
            request.app.state.settings,clock=request.app.state.clock)
    except AuthenticationError:raise authentication_required() from None
    except ListingUnavailable:raise HTTPException(status_code=404,detail='Listing is unavailable.') from None
    return ListingEditResponse.model_validate(listing)


@router.patch('/listings/{listing_id}',response_model=ListingEditResponse,openapi_extra={'requestBody':{'required':True,'content':{'application/json':{'schema':ListingEditRequest.model_json_schema()}}}})
def edit_listing(listing_id:Annotated[int,Path(ge=1,le=9223372036854775807)],request:Request,user=Depends(require_verified_user),payload=Depends(exact_edit_payload)):
    try:
        listing=update_own_listing(request.app.state.database,user.id,
            request.headers['authorization'].split(' ',1)[1],listing_id,payload,
            request.app.state.settings,clock=request.app.state.clock)
    except AuthenticationError:raise authentication_required() from None
    except ListingUnavailable:raise HTTPException(status_code=404,detail='Listing is unavailable.') from None
    except ListingEditForbidden:raise HTTPException(status_code=409,detail='This listing cannot be edited. Rejected listings must be deleted and recreated.') from None
    return ListingEditResponse.model_validate(listing)


async def require_empty_action(request,error_detail):
    raw=bytearray()
    async for chunk in request.stream():
        if len(raw)+len(chunk)>1024:raise HTTPException(status_code=422,detail=error_detail)
        raw.extend(chunk)
    try:
        if request.query_params or (raw and json.loads(raw)!={}):raise ValueError()
    except (ValueError,TypeError):raise HTTPException(status_code=422,detail=error_detail) from None


@router.post('/listings/{listing_id}/sold')
async def mark_sold(listing_id:Annotated[int,Path(ge=1,le=9223372036854775807)],request:Request,user=Depends(require_verified_user)):
    await require_empty_action(request,'Sold requests accept no fields.')
    from starlette.concurrency import run_in_threadpool
    try:
        return await run_in_threadpool(mark_own_listing_sold,request.app.state.database,user.id,
            request.headers['authorization'].split(' ',1)[1],listing_id,
            request.app.state.settings,clock=request.app.state.clock)
    except AuthenticationError:raise authentication_required() from None
    except ListingUnavailable:raise HTTPException(status_code=404,detail='Listing is unavailable.') from None
    except ListingSoldForbidden:raise HTTPException(status_code=409,detail='Only Active listings can be marked Sold.') from None


@router.delete('/listings/{listing_id}')
async def delete_listing(listing_id:Annotated[int,Path(ge=1,le=9223372036854775807)],request:Request,user=Depends(require_verified_user)):
    await require_empty_action(request,'Deletion requests accept no fields.')
    from starlette.concurrency import run_in_threadpool
    try:
        return await run_in_threadpool(delete_own_listing,request.app.state.database,user.id,
            request.headers['authorization'].split(' ',1)[1],listing_id,
            request.app.state.settings,clock=request.app.state.clock)
    except AuthenticationError:raise authentication_required() from None
    except ListingUnavailable:raise HTTPException(status_code=404,detail='Listing is unavailable.') from None
