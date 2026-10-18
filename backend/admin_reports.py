"""Minimal all-state listing-report queue and independent review timestamp."""
from datetime import timezone
from sqlalchemy import select,func
from backend.admin import locked_admin_user
from backend.models import Listing,ListingReport

class AdminReportUnavailable(Exception):pass

def admin_reports_page(database,actor_id,token,settings,*,limit,offset,state,clock):
 with database.session() as session:
  locked_admin_user(session,actor_id,token,settings,clock)
  filters=[ListingReport.reviewed_at.is_(None)] if state=='unreviewed' else [ListingReport.reviewed_at.is_not(None)] if state=='reviewed' else []
  total=session.scalar(select(func.count()).select_from(ListingReport).where(*filters))
  rows=session.execute(select(ListingReport,Listing).join(Listing,ListingReport.listing_id==Listing.id).where(*filters).order_by(ListingReport.created_at.desc(),ListingReport.id.desc()).limit(limit).offset(offset)).all()
  return {'items':[{'id':report.id,'reason':report.reason,'created_at':report.created_at,'reviewed_at':report.reviewed_at,'listing':{'id':listing.id,'title':listing.title,'status':listing.status,'url':f'/admin/listings/{listing.id}'}} for report,listing in rows],'total':total,'count':len(rows),'limit':limit,'offset':offset,'state':state}

def mark_admin_report_reviewed(database,actor_id,token,report_id,settings,*,clock):
 with database.session() as session:
  locked_admin_user(session,actor_id,token,settings,clock)
  listing_id=session.scalar(select(ListingReport.listing_id).where(ListingReport.id==report_id))
  if listing_id is None:raise AdminReportUnavailable()
  listing=session.scalar(select(Listing).where(Listing.id==listing_id).with_for_update())
  if listing is None:raise AdminReportUnavailable()
  report=session.scalar(select(ListingReport).where(ListingReport.id==report_id,ListingReport.listing_id==listing_id).with_for_update().execution_options(populate_existing=True))
  if report is None:raise AdminReportUnavailable()
  if report.reviewed_at is None:report.reviewed_at=clock();session.flush()
  result={'id':report.id,'reviewed_at':report.reviewed_at.astimezone(timezone.utc)}
 return result
