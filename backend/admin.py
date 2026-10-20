"""Explicit existing-account provisioning and current-role authorization."""
import argparse
from fastapi import Depends,HTTPException,Request
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from pydantic import ValidationError
from backend.authentication import require_verified_user,AuthenticationError,authentication_required
from backend.avatars import locked_avatar_user
from backend.config import load_settings,ConfigurationError
from backend.database import Database
from backend.models import User
from backend.schemas import UniversityEmailRequest

class AdminAccessDenied(Exception):pass
class AdminProvisioningError(Exception):pass

def promote_existing_admin(database,email):
 try:normalized=UniversityEmailRequest.model_validate({'email':email}).email
 except ValidationError:raise AdminProvisioningError() from None
 with database.session() as session:
  user=session.scalar(select(User).where(User.email==normalized).with_for_update())
  if user is None or not user.verified or user.suspended:raise AdminProvisioningError()
  user.role='admin';session.flush()

def locked_admin_user(session,user_id,token,settings,clock):
 user=locked_avatar_user(session,user_id,token,settings,clock)
 if user.role!='admin':raise AdminAccessDenied()
 return user

def require_admin_user(request:Request,user=Depends(require_verified_user)):
 try:
  with request.app.state.database.session() as session:
   return locked_admin_user(session,user.id,request.headers['authorization'].split(' ',1)[1],request.app.state.settings,request.app.state.clock)
 except AuthenticationError:raise authentication_required() from None
 except AdminAccessDenied:raise HTTPException(status_code=403,detail='Administrator access required.') from None

def main(argv=None, *, database=None):
 parser=argparse.ArgumentParser(description='Explicitly promote an existing eligible university account')
 parser.add_argument('--email',required=True);args=parser.parse_args(argv);owns_database=database is None
 try:
  if owns_database:database=Database(load_settings())
  promote_existing_admin(database,args.email)
 except (AdminProvisioningError,ConfigurationError,SQLAlchemyError):
  print('Admin provisioning could not be completed; verify account eligibility and operator configuration.');return 1
 finally:
  if owns_database and database is not None:database.dispose()
 print('Admin provisioning completed.');return 0

if __name__=='__main__':raise SystemExit(main())
