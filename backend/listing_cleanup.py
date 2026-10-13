"""Explicit local recovery limited to generated files of an absent listing."""
import argparse
import re

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from backend.config import ConfigurationError,load_settings
from backend.database import Database
from backend.images import ImageStorage,ImageStorageError
from backend.models import Listing


def cleanup_absent_listing(database,settings,listing_id,confirmed_id):
    if isinstance(listing_id,bool) or not isinstance(listing_id,int) or not 1<=listing_id<=9223372036854775807 or isinstance(confirmed_id,bool) or not isinstance(confirmed_id,int) or confirmed_id!=listing_id:
        raise ValueError('Confirm the exact positive listing identifier')
    with database.session() as session:
        if session.scalar(select(Listing.id).where(Listing.id==listing_id)) is not None:
            raise ValueError('Recovery requires an absent listing')
    storage=ImageStorage(settings.upload_dir,namespace='listings')
    folder=storage.path(f'listings/{listing_id}/'+ '0'*32+'.png',listing_id).parent
    if not folder.exists():return False
    pending=False
    try:files=list(folder.iterdir())
    except OSError:raise ImageStorageError('Cleanup is unavailable') from None
    for file in files:
        if not re.fullmatch(r'[0-9a-f]{32}\.(jpg|png|webp)',file.name):continue
        relative=f'listings/{listing_id}/{file.name}'
        path=storage.path(relative,listing_id)
        if path.is_dir():continue
        try:storage.delete(relative,listing_id)
        except ImageStorageError:pending=True
    return pending


def main(argv=None):
    parser=argparse.ArgumentParser(description='Clean generated orphan photos for an absent listing only')
    parser.add_argument('listing_id',type=int)
    parser.add_argument('--confirm-listing-id',required=True,type=int)
    args=parser.parse_args(argv)
    database=None
    try:
        settings=load_settings();database=Database(settings)
        pending=cleanup_absent_listing(database,settings,args.listing_id,args.confirm_listing_id)
    except (ValueError,ConfigurationError,SQLAlchemyError,ImageStorageError):
        print('Scoped listing cleanup could not be completed; verify the identifier, database and confined upload root.')
        return 1
    finally:
        if database is not None:database.dispose()
    print('Scoped listing cleanup remains pending.' if pending else 'Scoped listing cleanup completed; unrelated files preserved.')
    return 1 if pending else 0

if __name__=='__main__':raise SystemExit(main())
