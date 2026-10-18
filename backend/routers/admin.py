from typing import Annotated
from fastapi import APIRouter,Depends,Request,HTTPException,Path
from backend.authentication import AuthenticationError,authentication_required
from backend.admin import AdminAccessDenied
from backend.admin_users import admin_users_page,set_student_suspension,AdminTargetUnavailable,AdminTargetForbidden
from backend.admin_schemas import AdminUsersPage,SuspensionRequest
from backend.routers.listings import read_exact_listing_payload
from backend.admin import require_admin_user
router=APIRouter(prefix='/admin',tags=['administration'])
@router.get('/me')
def admin_identity(user=Depends(require_admin_user)):return {'id':user.id,'is_admin':True}


def user_page_query(request:Request):
 try:
  import re
  values={}
  for key,value in request.query_params.multi_items():
   if key not in {'limit','offset'} or key in values or not re.fullmatch(r'(?:0|[1-9][0-9]*)',value):raise ValueError()
   values[key]=value
  limit=int(values.get('limit','20'));offset=int(values.get('offset','0'))
  if not 1<=limit<=50 or not 0<=offset<=9223372036854775807:raise ValueError()
  return {'limit':limit,'offset':offset}
 except (ValueError,OverflowError):raise HTTPException(status_code=422,detail='Invalid admin user query.') from None


@router.get('/users',response_model=AdminUsersPage)
def users(request:Request,user=Depends(require_admin_user),query=Depends(user_page_query)):
 try:return admin_users_page(request.app.state.database,user.id,request.headers['authorization'].split(' ',1)[1],request.app.state.settings,clock=request.app.state.clock,**query)
 except AuthenticationError:raise authentication_required() from None
 except AdminAccessDenied:raise HTTPException(status_code=403,detail='Administrator access required.') from None


async def suspension_payload(request:Request):
 if request.query_params:raise HTTPException(status_code=422,detail='Invalid suspension request.')
 return await read_exact_listing_payload(request,SuspensionRequest,'Invalid suspension request.')


@router.patch('/users/{target_id}/suspension',openapi_extra={'requestBody':{'required':True,'content':{'application/json':{'schema':SuspensionRequest.model_json_schema()}}}})
def suspension(target_id:Annotated[int,Path(ge=1,le=9223372036854775807)],request:Request,user=Depends(require_admin_user),payload=Depends(suspension_payload)):
 try:return set_student_suspension(request.app.state.database,user.id,request.headers['authorization'].split(' ',1)[1],target_id,payload.suspended,request.app.state.settings,clock=request.app.state.clock)
 except AuthenticationError:raise authentication_required() from None
 except AdminAccessDenied:raise HTTPException(status_code=403,detail='Administrator access required.') from None
 except AdminTargetUnavailable:raise HTTPException(status_code=404,detail='Account is unavailable.') from None
 except AdminTargetForbidden:raise HTTPException(status_code=400,detail='Only other student accounts can be changed.') from None


from io import BytesIO
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from backend.admin_schemas import AdminListingsPage,AdminListingDetail
from backend.admin_listings import admin_listings_page,admin_listing_detail,admin_listing_photo,remove_admin_listing,AdminListingUnavailable
from backend.images import ImageStorageError
from backend.routers.listings import require_empty_action


def listing_page_query(request:Request):
 try:
  import re
  values={}
  for key,value in request.query_params.multi_items():
   if key not in {'limit','offset','status'} or key in values:raise ValueError()
   if key!='status' and not re.fullmatch(r'(?:0|[1-9][0-9]*)',value):raise ValueError()
   values[key]=value
  limit=int(values.get('limit','20'));offset=int(values.get('offset','0'));status=values.get('status')
  if not 1<=limit<=50 or not 0<=offset<=9223372036854775807 or (status is not None and status not in {'pending','active','sold','rejected','removed'}):raise ValueError()
  return {'limit':limit,'offset':offset,'status':status}
 except (ValueError,OverflowError):raise HTTPException(status_code=422,detail='Invalid admin listing query.') from None


def listing_call(request,user,operation,*args,**kwargs):
 try:return operation(request.app.state.database,user.id,request.headers['authorization'].split(' ',1)[1],*args,settings=request.app.state.settings,clock=request.app.state.clock,**kwargs)
 except AuthenticationError:raise authentication_required() from None
 except AdminAccessDenied:raise HTTPException(status_code=403,detail='Administrator access required.') from None
 except AdminListingUnavailable:raise HTTPException(status_code=404,detail='Listing is unavailable.') from None
 except ImageStorageError:raise HTTPException(status_code=500,detail='Listing photo storage is temporarily unavailable.') from None


@router.get('/listings',response_model=AdminListingsPage)
def review_listings(request:Request,user=Depends(require_admin_user),query=Depends(listing_page_query)):
 return listing_call(request,user,admin_listings_page,**query)


@router.get('/listings/{listing_id}',response_model=AdminListingDetail)
def review_listing(listing_id:Annotated[int,Path(ge=1,le=9223372036854775807)],request:Request,user=Depends(require_admin_user)):
 return listing_call(request,user,admin_listing_detail,listing_id)


@router.get('/listings/{listing_id}/photos/{photo_id}')
def review_photo(listing_id:Annotated[int,Path(ge=1,le=9223372036854775807)],photo_id:Annotated[int,Path(ge=1,le=9223372036854775807)],request:Request,user=Depends(require_admin_user)):
 image,media=listing_call(request,user,admin_listing_photo,listing_id,photo_id)
 return StreamingResponse(BytesIO(image),media_type=media,headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})


@router.post('/listings/{listing_id}/remove')
async def remove_listing(listing_id:Annotated[int,Path(ge=1,le=9223372036854775807)],request:Request,user=Depends(require_admin_user)):
 await require_empty_action(request,'Removal requests accept no fields.')
 return await run_in_threadpool(listing_call,request,user,remove_admin_listing,listing_id)


from backend.admin_schemas import AdminReportsPage
from backend.admin_reports import admin_reports_page,mark_admin_report_reviewed,AdminReportUnavailable


def report_page_query(request:Request):
 try:
  import re
  values={}
  for key,value in request.query_params.multi_items():
   if key not in {'limit','offset','state'} or key in values:raise ValueError()
   if key!='state' and not re.fullmatch(r'(?:0|[1-9][0-9]*)',value):raise ValueError()
   values[key]=value
  limit=int(values.get('limit','20'));offset=int(values.get('offset','0'));state=values.get('state','unreviewed')
  if not 1<=limit<=50 or not 0<=offset<=9223372036854775807 or state not in {'unreviewed','reviewed','all'}:raise ValueError()
  return {'limit':limit,'offset':offset,'state':state}
 except (ValueError,OverflowError):raise HTTPException(status_code=422,detail='Invalid admin report query.') from None


def report_call(request,user,operation,*args,**kwargs):
 try:return operation(request.app.state.database,user.id,request.headers['authorization'].split(' ',1)[1],*args,settings=request.app.state.settings,clock=request.app.state.clock,**kwargs)
 except AuthenticationError:raise authentication_required() from None
 except AdminAccessDenied:raise HTTPException(status_code=403,detail='Administrator access required.') from None
 except AdminReportUnavailable:raise HTTPException(status_code=404,detail='Report is unavailable.') from None


@router.get('/reports',response_model=AdminReportsPage)
def review_reports(request:Request,user=Depends(require_admin_user),query=Depends(report_page_query)):
 return report_call(request,user,admin_reports_page,**query)


@router.post('/reports/{report_id}/review')
async def review_report(report_id:Annotated[int,Path(ge=1,le=9223372036854775807)],request:Request,user=Depends(require_admin_user)):
 await require_empty_action(request,'Review requests accept no fields.')
 return await run_in_threadpool(report_call,request,user,mark_admin_report_reviewed,report_id)


from backend.publication import decide_publication,PublicationConflict,SellerPublicationIneligible
from backend.admin_schemas import ListingRejectionRequest


def publication_call(request,user,listing_id,**kwargs):
 try:return listing_call(request,user,decide_publication,listing_id,**kwargs)
 except SellerPublicationIneligible:raise HTTPException(status_code=409,detail='Seller must be verified and unsuspended before approval.') from None
 except PublicationConflict:raise HTTPException(status_code=409,detail='Listing decision conflicts with its current state. Reload review.') from None


@router.post('/listings/{listing_id}/approve')
async def approve_listing(listing_id:Annotated[int,Path(ge=1,le=9223372036854775807)],request:Request,user=Depends(require_admin_user)):
 await require_empty_action(request,'Approval requests accept no fields.')
 return await run_in_threadpool(publication_call,request,user,listing_id)


async def rejection_payload(request:Request):
 if request.query_params:raise HTTPException(status_code=422,detail='Invalid rejection request.')
 return await read_exact_listing_payload(request,ListingRejectionRequest,'Invalid rejection request.')


@router.post('/listings/{listing_id}/reject',openapi_extra={'requestBody':{'required':True,'content':{'application/json':{'schema':ListingRejectionRequest.model_json_schema()}}}})
def reject_listing(listing_id:Annotated[int,Path(ge=1,le=9223372036854775807)],request:Request,user=Depends(require_admin_user),payload=Depends(rejection_payload)):
 return publication_call(request,user,listing_id,reason=payload.reason)
