"""Explicit manual publication decisions with ordered account locks."""
from datetime import timezone
from sqlalchemy import select
from backend.admin import locked_admin_user
from backend.admin_listings import AdminListingUnavailable
from backend.models import User,Listing

class PublicationConflict(Exception):pass
class SellerPublicationIneligible(PublicationConflict):pass

def decide_publication(database,actor_id,token,listing_id,settings,*,clock,reason=None):
 with database.session() as session:
  owner_id=session.scalar(select(Listing.owner_id).where(Listing.id==listing_id))
  # Discovery is not a lock; acquire all accounts by id before the listing.
  locked={}
  for id in sorted({actor_id} if owner_id is None else {actor_id,owner_id}):
   locked[id]=session.scalar(select(User).where(User.id==id).with_for_update())
  locked_admin_user(session,actor_id,token,settings,clock)
  listing=session.scalar(select(Listing).where(Listing.id==listing_id).with_for_update())
  if listing is None or owner_id is None or locked.get(owner_id) is None:raise AdminListingUnavailable()
  if listing.owner_id!=owner_id:raise PublicationConflict()
  seller=locked[owner_id]
  if reason is None:
   if not seller.verified or seller.suspended:raise SellerPublicationIneligible()
   if listing.status=='pending':listing.status='active';listing.published_at=clock()
   elif listing.status!='active':raise PublicationConflict()
  else:
   if listing.status=='pending':listing.status='rejected';listing.rejection_reason=reason
   elif listing.status!='rejected' or listing.rejection_reason!=reason:raise PublicationConflict()
  session.flush()
  result={'id':listing.id,'status':listing.status,'published_at':listing.published_at.astimezone(timezone.utc) if listing.published_at is not None else None,'rejection_reason':listing.rejection_reason if listing.status=='rejected' else None}
 return result
