from fastapi import APIRouter, HTTPException, Request

from backend.registration import DuplicateEmailError, register_student
from backend.schemas import RegistrationRequest, RegistrationResponse


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", status_code=201, response_model=RegistrationResponse)
def register(payload: RegistrationRequest, request: Request):
    try:
        user = register_student(request.app.state.database, payload.email, payload.password.get_secret_value())
    except DuplicateEmailError:
        raise HTTPException(status_code=409, detail="University email is already registered.") from None
    return RegistrationResponse(id=user.id, email=user.email, verified=user.verified)
