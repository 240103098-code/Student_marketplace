"""Explicit absence-checked retry; never retain deleted account identity."""
import argparse
import re
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from backend.config import ConfigurationError,load_settings
from backend.database import Database
from backend.models import User,Listing
from backend.images import ImageStorage,ImageStorageError
from backend.listing_cleanup import cleanup_absent_listing


def cleanup_absent_account(database,settings,user_id,confirmed_id,listing_ids=(),confirmed_listing_ids=()):
 def valid(id):return type(id) is int and 1<=id<=9223372036854775807
 if not valid(user_id) or type(confirmed_id) is not int or user_id!=confirmed_id:raise ValueError('Confirm exact account id')
 ids=list(listing_ids);confirmed=list(confirmed_listing_ids)
 if ids!=confirmed or len(ids)!=len(set(ids)) or any(not valid(id) for id in ids):raise ValueError('Confirm exact captured listing ids')
 with database.session() as session:
  if session.get(User,user_id) is not None or (ids and session.scalar(select(Listing.id).where(Listing.id.in_(ids)).limit(1)) is not None):raise ValueError('Recovery requires absent account and listings')
 storage=ImageStorage(settings.upload_dir)
 folder=storage.path(f'avatars/{user_id}/'+ '0'*32+'.png',user_id).parent
 pending=False
 if folder.exists():
  try:files=list(folder.iterdir())
  except OSError:raise ImageStorageError('Cleanup is unavailable') from None
  for file in files:
   if not re.fullmatch(r'[0-9a-f]{32}\.(jpg|png|webp)',file.name):continue
   relative=f'avatars/{user_id}/{file.name}'
   if storage.path(relative,user_id).is_dir():continue
   try:storage.delete(relative,user_id)
   except ImageStorageError:pending=True
 for id in ids:pending=cleanup_absent_listing(database,settings,id,id) or pending
 return pending


def main(argv=None):
 parser=argparse.ArgumentParser(description='Retry generated images of an absent account and explicitly captured absent listings')
 parser.add_argument('user_id',type=int);parser.add_argument('--confirm-user-id',type=int,required=True)
 parser.add_argument('--listing-id',type=int,action='append',default=[]);parser.add_argument('--confirm-listing-id',type=int,action='append',default=[])
 args=parser.parse_args(argv);database=None
 try:
  settings=load_settings();database=Database(settings)
  pending=cleanup_absent_account(database,settings,args.user_id,args.confirm_user_id,args.listing_id,args.confirm_listing_id)
 except (ValueError,ConfigurationError,SQLAlchemyError,ImageStorageError):
  print('Scoped account cleanup could not be completed; verify confirmed identifiers, absence and confined storage.');return 1
 finally:
  if database is not None:database.dispose()
 print('Scoped account cleanup remains pending.' if pending else 'Scoped account cleanup completed; unrelated files preserved.')
 return 1 if pending else 0

if __name__=='__main__':raise SystemExit(main())
