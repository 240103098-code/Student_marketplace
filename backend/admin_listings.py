"""All-state admin listing inspection and retained-record removal."""
from sqlalchemy import select,func
from backend.admin import locked_admin_user
from backend.models import Listing,ListingPhoto,User
from backend.images import ImageStorage

class AdminListingUnavailable(Exception):pass

def lock_review_listing(session,actor_id,token,listing_id,settings,clock):
 locked_admin_user(session,actor_id,token,settings,clock)
 listing=session.scalar(select(Listing).where(Listing.id==listing_id).with_for_update())
 if listing is None:raise AdminListingUnavailable()
 return listing

def summary(listing,seller):
 result={key:getattr(listing,key) for key in ['id','title','price','currency','category_id','condition','status','created_at','published_at']}
 result['seller']={key:getattr(seller,key) for key in ['id','email','name']}
 return result

def admin_listings_page(database,actor_id,token,settings,*,limit,offset,status,clock):
 with database.session() as session:
  locked_admin_user(session,actor_id,token,settings,clock)
  filters=[] if status is None else [Listing.status==status]
  total=session.scalar(select(func.count()).select_from(Listing).where(*filters))
  rows=session.execute(select(Listing,User).join(User,Listing.owner_id==User.id).where(*filters).order_by(Listing.created_at.desc(),Listing.id.desc()).limit(limit).offset(offset)).all()
  return {'items':[summary(listing,seller) for listing,seller in rows],'total':total,'count':len(rows),'limit':limit,'offset':offset,'status':status}

def admin_listing_detail(database,actor_id,token,listing_id,settings,*,clock):
 with database.session() as session:
  listing=lock_review_listing(session,actor_id,token,listing_id,settings,clock)
  data=summary(listing,session.get(User,listing.owner_id));data['description']=listing.description;data['rejection_reason']=listing.rejection_reason if listing.status=='rejected' else None;data['photos']=[]
  for photo in session.scalars(select(ListingPhoto).where(ListingPhoto.listing_id==listing_id).order_by(ListingPhoto.position)):
   data['photos'].append({'id':photo.id,'position':photo.position,'is_main':not data['photos'],'url':f'/admin/listings/{listing_id}/photos/{photo.id}'})
  return data

def admin_listing_photo(database,actor_id,token,listing_id,photo_id,settings,*,clock):
 with database.session() as session:
  lock_review_listing(session,actor_id,token,listing_id,settings,clock)
  photo=session.scalar(select(ListingPhoto).where(ListingPhoto.id==photo_id,ListingPhoto.listing_id==listing_id))
  if photo is None:raise AdminListingUnavailable()
  image=ImageStorage(settings.upload_dir,namespace='listings').read(photo.storage_path,listing_id)
  if image is None:raise AdminListingUnavailable()
  return image

def remove_admin_listing(database,actor_id,token,listing_id,settings,*,clock):
 with database.session() as session:
  listing=lock_review_listing(session,actor_id,token,listing_id,settings,clock);listing.status='removed';session.flush()
  result={'id':listing.id,'status':'removed','published_at':listing.published_at}
 return result
