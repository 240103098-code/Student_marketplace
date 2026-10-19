from backend.abuse import quota,email_quota,peer
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from backend.registration import DuplicateEmailError, register_student
from backend.schemas import RegistrationRequest, RegistrationResponse, AuthMeResponse, VerifyEmailRequest, ResendVerificationRequest, LoginRequest, AccessTokenResponse, ChangePasswordRequest, ForgotPasswordRequest, ResetPasswordRequest
from backend.mail import EmailDeliveryError
from backend.verification import verify_registration_code, resend_registration_code
from backend.authentication import AuthenticationError, authenticate_student, require_verified_user
from backend.tokens import issue_access_token
from backend.sessions import COOKIE_NAME, validate_origin, validate_csrf_header, new_login_session, rotate_refresh_session, logout_session, retrieve_csrf, set_refresh_cookie, clear_refresh_cookie
from backend.authentication import authentication_required


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", status_code=201, response_model=RegistrationResponse)
def register(payload: RegistrationRequest, request: Request):
    email_quota(request,payload.email)
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
    email_quota(request,payload.email)
    try:
        resend_registration_code(request.app.state.database, payload.email,
            request.app.state.settings, request.app.state.email_sender, clock=request.app.state.clock)
    except EmailDeliveryError:
        raise HTTPException(status_code=503, detail="Verification email is temporarily unavailable.") from None
    response.headers["Retry-After"] = "60"
    return {"detail": "If this address is eligible, a verification email may arrive. Retry after 60 seconds."}


@router.post("/login", response_model=AccessTokenResponse)
def login(payload: LoginRequest, request: Request, response: Response):
    validate_origin(request.app.state.settings, request.headers.get("origin"))
    reservation=quota(request,('login-failure',payload.email+'|'+peer(request),10,900))
    try:
        user = authenticate_student(request.app.state.database, payload.email, payload.password.get_secret_value())
        grant = new_login_session(request.app.state.database, user.id, request.app.state.settings, clock=request.app.state.clock, verified_password_hash=user.password_hash)
    except AuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid credentials or account unavailable.", headers={"WWW-Authenticate": "Bearer"}) from None
    except BaseException:
        request.app.state.limiter.refund(reservation)
        raise
    request.app.state.limiter.refund(reservation)
    token = issue_access_token(request.app.state.settings, user.id, grant.family_id, clock=request.app.state.clock)
    set_refresh_cookie(response, grant, request.app.state.settings, request.app.state.clock())
    return AccessTokenResponse(access_token=token, expires_in=request.app.state.settings.jwt_access_minutes * 60)


@router.get("/me", response_model=AuthMeResponse)
def current_account(user=Depends(require_verified_user)):
    return AuthMeResponse(id=user.id, email=user.email, verified=user.verified,is_admin=user.role=="admin")


def mutation_csrf(request):
    validate_origin(request.app.state.settings, request.headers.get("origin"), required=True)
    submitted = request.headers.get("x-csrf-token")
    validate_csrf_header(submitted)
    return submitted


@router.get("/csrf")
def csrf_bootstrap(request: Request, response: Response):
    validate_origin(request.app.state.settings, request.headers.get("origin"))
    value = retrieve_csrf(request.app.state.database, request.cookies.get(COOKIE_NAME), request.app.state.settings, clock=request.app.state.clock)
    if value is None:
        raise authentication_required()
    response.headers["Cache-Control"] = "no-store"
    return {"csrf_token": value}


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(request: Request, response: Response):
    submitted = mutation_csrf(request)
    grant = rotate_refresh_session(request.app.state.database, request.cookies.get(COOKIE_NAME), submitted, request.app.state.settings, clock=request.app.state.clock)
    if grant is None:
        raise authentication_required()
    token = issue_access_token(request.app.state.settings, grant.user_id, grant.family_id, clock=request.app.state.clock)
    set_refresh_cookie(response, grant, request.app.state.settings, request.app.state.clock())
    return AccessTokenResponse(access_token=token, expires_in=request.app.state.settings.jwt_access_minutes * 60)


@router.post("/logout", status_code=204)
def logout(request: Request):
    submitted = mutation_csrf(request)
    logout_session(request.app.state.database, request.cookies.get(COOKIE_NAME), submitted, request.app.state.settings, clock=request.app.state.clock)
    response = Response(status_code=204)
    clear_refresh_cookie(response, request.app.state.settings)
    return response


@router.post("/change-password", status_code=204)
def change_password(payload: ChangePasswordRequest, request: Request, user=Depends(require_verified_user)):
    from backend.passwords import WrongCurrentPassword, change_student_password

    try:
        change_student_password(request.app.state.database, user.id,
            request.headers["authorization"].split(" ", 1)[1],
            payload.current_password.get_secret_value(), payload.new_password.get_secret_value(),
            request.app.state.settings, clock=request.app.state.clock)
    except WrongCurrentPassword:
        raise HTTPException(status_code=400, detail="Current password is incorrect.") from None
    except AuthenticationError:
        raise authentication_required() from None
    response = Response(status_code=204)
    clear_refresh_cookie(response, request.app.state.settings)
    return response


@router.post("/forgot-password", status_code=202)
def forgot_password(payload: ForgotPasswordRequest, request: Request, response: Response):
    from backend.recovery import request_password_reset

    email_quota(request,payload.email)
    try:
        request_password_reset(request.app.state.database, payload.email,
            request.app.state.settings, request.app.state.email_sender, clock=request.app.state.clock)
    except EmailDeliveryError:
        pass  # Issuance transaction rolled back; response never reveals eligibility/delivery.
    response.headers["Retry-After"] = "60"
    return {"detail": "If this address is eligible, a password-reset email may arrive. Retry after 60 seconds."}


@router.post("/reset-password", status_code=204)
def reset_password(payload: ResetPasswordRequest, request: Request):
    from backend.recovery import reset_student_password

    if not reset_student_password(request.app.state.database, payload.email,
        payload.code.get_secret_value(), payload.new_password.get_secret_value(),
        request.app.state.settings, clock=request.app.state.clock):
        raise HTTPException(status_code=400, detail="Password-reset code is invalid or unavailable.")
    response = Response(status_code=204)
    clear_refresh_cookie(response, request.app.state.settings)
    return response
