from fastapi import APIRouter, Depends, Request

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
