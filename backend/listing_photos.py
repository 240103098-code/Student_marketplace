"""Pending-owner photo append and linked private binary access."""

from sqlalchemy import select

from backend.avatars import locked_avatar_user
from backend.images import ImageStorage, ImageStorageError, canonical_image
from backend.models import Listing, ListingPhoto, User


class ListingPhotoUnavailable(Exception):
    pass


class ListingPhotoConflict(Exception):
    def __init__(self,limit=False):self.limit=limit


def append_listing_photo(database,user_id,token,listing_id,raw,settings,*,clock):
    storage=ImageStorage(settings.upload_dir,namespace='listings')
    created=None
    try:
        with database.session() as session:
            locked_avatar_user(session,user_id,token,settings,clock)
            # All photo mutations lock the acting account before the listing.
            listing=session.scalar(select(Listing).where(Listing.id==listing_id).with_for_update())
            if listing is None or listing.owner_id != user_id:raise ListingPhotoUnavailable()
            if listing.status != 'pending':raise ListingPhotoConflict()
            positions=list(session.scalars(select(ListingPhoto.position).where(ListingPhoto.listing_id==listing_id)))
            position=max(positions,default=0)+1
            if len(positions)>=5 or position>5:raise ListingPhotoConflict(limit=True)
            image=canonical_image(raw)
            created=storage.write(image,listing_id)
            photo=ListingPhoto(listing_id=listing_id,storage_path=created,position=position)
            session.add(photo);session.flush()
        return {'id':photo.id,'listing_id':listing_id,'position':position,'is_main':position==1,
                'url':f'/listings/{listing_id}/photos/{photo.id}'}
    except BaseException:
        if created is not None:
            try:storage.delete(created,listing_id)
            except ImageStorageError:pass  # Possible orphan; documented, never delete old/unrelated files.
        raise


def read_listing_photo(database,user_id,token,listing_id,photo_id,settings,*,clock):
    with database.session() as session:
        locked_avatar_user(session,user_id,token,settings,clock)
        listing=session.scalar(select(Listing).where(Listing.id==listing_id).with_for_update())
        if listing is None or listing.status=='removed':raise ListingPhotoUnavailable()
        if listing.owner_id==user_id:
            if listing.status not in {'pending','active','sold','rejected'}:raise ListingPhotoUnavailable()
        else:
            seller=session.get(User,listing.owner_id)
            if listing.status != 'active' or seller is None or not seller.verified or seller.suspended:
                raise ListingPhotoUnavailable()
        photo=session.scalar(select(ListingPhoto).where(ListingPhoto.id==photo_id,ListingPhoto.listing_id==listing_id))
        if photo is None:raise ListingPhotoUnavailable()
        image=ImageStorage(settings.upload_dir,namespace='listings').read(photo.storage_path,listing_id)
        if image is None:raise ListingPhotoUnavailable()
        return image
