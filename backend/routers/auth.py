from fastapi import APIRouter, Depends, HTTPException, Request, Response

from backend.registration import DuplicateEmailError, register_student
from backend.schemas import RegistrationRequest, RegistrationResponse, VerifyEmailRequest, ResendVerificationRequest, LoginRequest, AccessTokenResponse
from backend.mail import EmailDeliveryError
from backend.verification import verify_registration_code, resend_registration_code
from backend.authentication import AuthenticationError, authenticate_student, require_verified_user
from backend.tokens import issue_access_token


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", status_code=201, response_model=RegistrationResponse)
def register(payload: RegistrationRequest, request: Request):
    try:
        user = register_student(request.app.state.database, payload.email,
            payload.password.get_secret_value(), request.app.state.settings, request.app.state.email_sender, clock=request.app.state.clock)
    except DuplicateEmailError:
        raise HTTPException(status_code=409, detail="University email is already registered.") from None
    except EmailDeliveryError:
        raise HTTPException(status_code=503, detail="Verification email is temporarily unavailable.") from None
    return RegistrationResponse(id=user.id, email=user.email, verified=user.verified)


@router.post("/verify-email")
def verify_email(payload: VerifyEmailRequest, request: Request):
    succeeded = verify_registration_code(request.app.state.database, payload.email,
        payload.code.get_secret_value(), request.app.state.settings, clock=request.app.state.clock)
    if not succeeded:
        raise HTTPException(status_code=400, detail="Verification code is invalid or unavailable.")
    return {"verified": True}


@router.post("/resend-verification", status_code=202)
def resend_verification(payload: ResendVerificationRequest, request: Request, response: Response):
    try:
        resend_registration_code(request.app.state.database, payload.email,
            request.app.state.settings, request.app.state.email_sender, clock=request.app.state.clock)
    except EmailDeliveryError:
        raise HTTPException(status_code=503, detail="Verification email is temporarily unavailable.") from None
    response.headers["Retry-After"] = "60"
    return {"detail": "If this address is eligible, a verification email may arrive. Retry after 60 seconds."}


@router.post("/login", response_model=AccessTokenResponse)
def login(payload: LoginRequest, request: Request):
    try:
        user = authenticate_student(request.app.state.database, payload.email, payload.password.get_secret_value())
    except AuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid credentials or account unavailable.", headers={"WWW-Authenticate": "Bearer"}) from None
    token = issue_access_token(request.app.state.settings, user.id, clock=request.app.state.clock)
    return AccessTokenResponse(access_token=token, expires_in=request.app.state.settings.jwt_access_minutes * 60)


@router.get("/me", response_model=RegistrationResponse)
def current_account(user=Depends(require_verified_user)):
    return RegistrationResponse(id=user.id, email=user.email, verified=user.verified)
