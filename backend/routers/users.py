from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.formparsers import MultiPartException
from fastapi.responses import StreamingResponse
from io import BytesIO

from backend.avatars import mutate_avatar, read_avatar
from backend.images import FORM_LIMIT, MAX_BYTES

from backend.authentication import AuthenticationError, authentication_required, require_verified_user
from backend.profile_schemas import ProfilePatch, ProfileResponse
from backend.profiles import update_own_profile


router = APIRouter(prefix='/users', tags=['own profile'])


@router.get('/me', response_model=ProfileResponse)
def own_profile(user=Depends(require_verified_user)):
    return ProfileResponse.model_validate(user)


@router.patch('/me', response_model=ProfileResponse)
def edit_own_profile(payload: ProfilePatch, request: Request, user=Depends(require_verified_user)):
    try:
        updated = update_own_profile(request.app.state.database, user.id,
            request.headers['authorization'].split(' ', 1)[1], payload,
            request.app.state.settings, clock=request.app.state.clock)
    except AuthenticationError:
        raise authentication_required() from None
    return ProfileResponse.model_validate(updated)


@router.post('/me/avatar')
async def upload_avatar(request: Request, user=Depends(require_verified_user)):
    consumed = 0
    async def limited_receive():
        nonlocal consumed
        message = await request.receive()
        consumed += len(message.get('body', b''))
        if consumed > FORM_LIMIT:
            raise MultiPartException('Avatar upload exceeds the request limit')
        return message
    limited = Request(request.scope, limited_receive)
    try:
        async with limited.form(max_files=1, max_fields=0, max_part_size=MAX_BYTES+1) as form:
            fields = list(form.multi_items())
            if len(fields) != 1 or fields[0][0] != 'image' or not isinstance(fields[0][1], UploadFile):
                raise HTTPException(status_code=400, detail='Submit exactly one image file.')
            raw = await fields[0][1].read(MAX_BYTES+1)
            if len(raw) > MAX_BYTES:
                raise HTTPException(status_code=413, detail='Image exceeds five MiB.')
    except StarletteHTTPException as error:
        if error.detail == 'Avatar upload exceeds the request limit':
            raise HTTPException(status_code=413, detail='Image exceeds five MiB.') from None
        if error.status_code == 413:
            raise
        raise HTTPException(status_code=400, detail='Submit exactly one image file.') from None
    try:
        pending = await run_in_threadpool(mutate_avatar, request.app.state.database, user.id,
            request.headers['authorization'].split(' ', 1)[1], request.app.state.settings,
            raw=raw, clock=request.app.state.clock)
    except AuthenticationError:
        raise authentication_required() from None
    return {'detail': 'Profile photo updated.', 'cleanup_pending': pending}


@router.get('/me/avatar')
def own_avatar(request: Request, user=Depends(require_verified_user)):
    try:
        image = read_avatar(request.app.state.database, user.id,
            request.headers['authorization'].split(' ', 1)[1], request.app.state.settings,
            clock=request.app.state.clock)
    except AuthenticationError:
        raise authentication_required() from None
    if image is None:
        raise HTTPException(status_code=404, detail='Profile photo is unavailable.')
    content, media_type = image
    return StreamingResponse(BytesIO(content), media_type=media_type,
        headers={'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'})


@router.delete('/me/avatar')
def remove_avatar(request: Request, user=Depends(require_verified_user)):
    try:
        pending = mutate_avatar(request.app.state.database, user.id,
            request.headers['authorization'].split(' ', 1)[1], request.app.state.settings,
            clock=request.app.state.clock)
    except AuthenticationError:
        raise authentication_required() from None
    return {'detail': 'Profile photo removed.', 'cleanup_pending': pending}
