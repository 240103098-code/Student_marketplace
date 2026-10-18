"""Permanent own-account removal; filesystem cleanup follows confirmed commit."""
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError,InvalidHashError
from sqlalchemy import select
from backend.avatars import locked_avatar_user
from backend.images import ImageStorage,ImageStorageError
from backend.models import Listing,ListingPhoto
from backend.passwords import WrongCurrentPassword


def delete_own_account(database,user_id,token,password,settings,*,clock):
 avatar_storage=ImageStorage(settings.upload_dir)
 photo_storage=ImageStorage(settings.upload_dir,'listings')
 with database.session() as session:
  user=locked_avatar_user(session,user_id,token,settings,clock)
  try:PasswordHasher().verify(user.password_hash,password)
  except (VerificationError,InvalidHashError):raise WrongCurrentPassword() from None
  listings=list(session.scalars(select(Listing).where(Listing.owner_id==user_id).order_by(Listing.id).with_for_update()))
  avatar=user.avatar_path
  if avatar is not None:avatar_storage.path(avatar,user_id)
  paths=[]
  for listing in listings:
   for path in session.scalars(select(ListingPhoto.storage_path).where(ListingPhoto.listing_id==listing.id)):
    photo_storage.path(path,listing.id);paths.append((listing.id,path))
  session.delete(user);session.flush()
 pending=False
 for storage,owner,path in ([(avatar_storage,user_id,avatar)] if avatar is not None else [])+[(photo_storage,id,path) for id,path in paths]:
  try:storage.delete(path,owner)
  except ImageStorageError:pending=True
 return {'deleted':True,'cleanup_pending':pending}
