"""Contact-gated creation with current account/session checks under lock."""

from pydantic import ValidationError
from sqlalchemy import select

from backend.authentication import AuthenticationError
from backend.models import Category, Listing, RefreshSession, User
from backend.profile_schemas import ProfilePatch
from backend.tokens import AccessTokenError, validate_access_token


class SellerContactRequired(Exception):
    pass


def has_valid_contact(user):
    for field in ['phone','telegram_username','external_contact_url']:
        value=getattr(user,field)
        if value is None:continue
        try:ProfilePatch.model_validate({field:value})
        except ValidationError:continue
        return True
    return False


def create_own_listing(database,user_id,token,payload,settings,*,clock):
    with database.session() as session:
        user=session.scalar(select(User).where(User.id==user_id).with_for_update())
        try:token_user_id,family=validate_access_token(settings,token,clock=clock)
        except AccessTokenError:raise AuthenticationError('Authentication required') from None
        if user is None or user.id != token_user_id or not user.verified or user.suspended:
            raise AuthenticationError('Authentication required')
        active=session.scalar(select(RefreshSession.id).where(RefreshSession.user_id==user_id,
            RefreshSession.family_id==family,RefreshSession.revoked_at.is_(None),RefreshSession.expires_at>clock()).limit(1))
        if active is None:raise AuthenticationError('Authentication required')
        if not has_valid_contact(user):raise SellerContactRequired()
        listing=Listing(owner_id=user_id,**payload.model_dump(),currency='KZT',status='pending',published_at=None)
        session.add(listing);session.flush()
        return listing


def fixed_categories(database):
    with database.session() as session:
        return [{'id':item.id,'key':item.key,'label':item.name} for item in session.scalars(select(Category).order_by(Category.id))]


class ListingUnavailable(Exception):
    pass


class ListingEditForbidden(Exception):
    pass


def locked_own_listing(session,user_id,token,listing_id,settings,clock):
    from backend.avatars import locked_avatar_user
    locked_avatar_user(session,user_id,token,settings,clock)
    listing=session.scalar(select(Listing).where(Listing.id==listing_id).with_for_update())
    if listing is None or listing.owner_id != user_id:raise ListingUnavailable()
    return listing


def read_own_listing_edit(database,user_id,token,listing_id,settings,*,clock):
    with database.session() as session:
        return locked_own_listing(session,user_id,token,listing_id,settings,clock)


def update_own_listing(database,user_id,token,listing_id,payload,settings,*,clock):
    with database.session() as session:
        listing=locked_own_listing(session,user_id,token,listing_id,settings,clock)
        if listing.status not in {'pending','active','sold'}:raise ListingEditForbidden()
        for field,value in payload.model_dump(exclude_unset=True).items():setattr(listing,field,value)
        session.flush()
        return listing
