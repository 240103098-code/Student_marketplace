from backend.abuse import user_quota
from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Path
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from backend.authentication import AuthenticationError, authentication_required, require_verified_user
from backend.image_uploads import read_image_upload
from backend.listing_photos import ListingPhotoConflict, ListingPhotoUnavailable, append_listing_photo, read_listing_photo

router=APIRouter(prefix='/listings',tags=['private listing photos'])


@router.post('/{listing_id}/photos',status_code=201)
async def upload_photo(listing_id:Annotated[int,Path(ge=1,le=9223372036854775807)],request:Request,user=Depends(require_verified_user)):
    user_quota(request,user,'image-upload',30)
    raw=await read_image_upload(request)
    try:
        return await run_in_threadpool(append_listing_photo,request.app.state.database,user.id,
            request.headers['authorization'].split(' ',1)[1],listing_id,raw,
            request.app.state.settings,clock=request.app.state.clock)
    except AuthenticationError:raise authentication_required() from None
    except ListingPhotoUnavailable:raise HTTPException(status_code=404,detail='Listing photo is unavailable.') from None
    except ListingPhotoConflict as error:
        detail='A listing can have at most five photos.' if error.limit else 'Photos can be added only to your Pending listing.'
        raise HTTPException(status_code=409,detail=detail) from None


@router.get('/{listing_id}/photos/{photo_id}')
def view_photo(listing_id:Annotated[int,Path(ge=1,le=9223372036854775807)],photo_id:Annotated[int,Path(ge=1,le=9223372036854775807)],request:Request,user=Depends(require_verified_user)):
    try:
        content,media=read_listing_photo(request.app.state.database,user.id,
            request.headers['authorization'].split(' ',1)[1],listing_id,photo_id,
            request.app.state.settings,clock=request.app.state.clock)
    except AuthenticationError:raise authentication_required() from None
    except ListingPhotoUnavailable:raise HTTPException(status_code=404,detail='Listing photo is unavailable.') from None
    return StreamingResponse(BytesIO(content),media_type=media,headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})
