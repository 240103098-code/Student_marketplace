"""Contact-gated creation with current account/session checks under lock."""

from pydantic import ValidationError
from sqlalchemy import select, func, or_

from backend.authentication import AuthenticationError
from backend.models import Category, Listing, ListingPhoto, RefreshSession, User
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


def own_listings_page(database,user_id,token,settings,*,limit,offset,status,clock):
    from backend.avatars import locked_avatar_user
    with database.session() as session:
        locked_avatar_user(session,user_id,token,settings,clock)
        filters=[Listing.owner_id==user_id]
        if status is not None:filters.append(Listing.status==status)
        total=session.scalar(select(func.count()).select_from(Listing).where(*filters))
        rows=list(session.scalars(select(Listing).where(*filters).order_by(Listing.created_at.desc(),Listing.id.desc()).limit(limit).offset(offset)))
        ids=[item.id for item in rows if item.status!='removed']
        photos={id:[] for id in ids}
        if ids:
            for photo in session.scalars(select(ListingPhoto).where(ListingPhoto.listing_id.in_(ids)).order_by(ListingPhoto.listing_id,ListingPhoto.position)):
                group=photos[photo.listing_id]
                group.append({'id':photo.id,'position':photo.position,'is_main':not group,'url':f'/listings/{photo.listing_id}/photos/{photo.id}'})
        items=[]
        for item in rows:
            data={field:getattr(item,field) for field in ['id','title','description','price','currency','category_id','condition','status','created_at','published_at']}
            data['rejection_reason']=item.rejection_reason if item.status=='rejected' else None
            data['photos']=photos.get(item.id,[])
            items.append(data)
        return {'items':items,'total':total,'count':len(items),'limit':limit,'offset':offset,'status':status}


class ListingSoldForbidden(Exception):
    pass


def mark_own_listing_sold(database,user_id,token,listing_id,settings,*,clock):
    with database.session() as session:
        listing=locked_own_listing(session,user_id,token,listing_id,settings,clock)
        if listing.status not in {'active','sold'}:raise ListingSoldForbidden()
        listing.status='sold'
        session.flush()
        return {'id':listing.id,'status':'sold','published_at':listing.published_at}


def delete_own_listing(database,user_id,token,listing_id,settings,*,clock):
    from backend.images import ImageStorage,ImageStorageError
    storage=ImageStorage(settings.upload_dir,namespace='listings')
    with database.session() as session:
        listing=locked_own_listing(session,user_id,token,listing_id,settings,clock)
        paths=list(session.scalars(select(ListingPhoto.storage_path).where(ListingPhoto.listing_id==listing_id)))
        for path in paths:storage.path(path,listing_id)
        session.delete(listing)
        session.flush()
    pending=False
    for path in paths:
        try:storage.delete(path,listing_id)
        except ImageStorageError:pending=True
    return {'id':listing_id,'deleted':True,'cleanup_pending':pending}


def browse_listings_page(database,user_id,token,settings,*,limit,offset,clock,q=None,category_id=None,condition=None,min_price=None,max_price=None):
    from backend.avatars import locked_avatar_user
    with database.session() as session:
        locked_avatar_user(session,user_id,token,settings,clock)
        visible=[Listing.status=='active',Listing.published_at.is_not(None),User.verified.is_(True),User.suspended.is_(False)]
        if q:
            visible.append(or_(Listing.title.icontains(q,autoescape=True,escape='!'),Listing.description.icontains(q,autoescape=True,escape='!')))
        if category_id is not None:visible.append(Listing.category_id==category_id)
        if condition is not None:visible.append(Listing.condition==condition)
        if min_price is not None:visible.append(Listing.price>=min_price)
        if max_price is not None:visible.append(Listing.price<=max_price)
        query=select(Listing).join(User,Listing.owner_id==User.id).where(*visible)
        total=session.scalar(select(func.count()).select_from(Listing).join(User,Listing.owner_id==User.id).where(*visible))
        rows=list(session.scalars(query.order_by(Listing.published_at.desc(),Listing.id.desc()).limit(limit).offset(offset)))
        ids=[item.id for item in rows]
        main={}
        if ids:
            for photo in session.scalars(select(ListingPhoto).where(ListingPhoto.listing_id.in_(ids)).order_by(ListingPhoto.listing_id,ListingPhoto.position)):
                if photo.listing_id not in main:
                    main[photo.listing_id]={'id':photo.id,'position':photo.position,'is_main':True,'url':f'/listings/{photo.listing_id}/photos/{photo.id}'}
        items=[]
        for row in rows:
            card={key:getattr(row,key) for key in ['id','title','price','currency','category_id','condition','published_at']}
            card['main_photo']=main.get(row.id)
            items.append(card)
        return {'items':items,'total':total,'count':len(items),'limit':limit,'offset':offset}
