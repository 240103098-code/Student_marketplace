"""Administrative reads and atomic suspension using deterministic account locks."""
from sqlalchemy import select,func
from backend.admin import locked_admin_user
from backend.models import User
from backend.sessions import revoke_user_sessions

class AdminTargetUnavailable(Exception):pass
class AdminTargetForbidden(Exception):pass

def admin_users_page(database,actor_id,token,settings,*,limit,offset,clock):
 with database.session() as session:
  locked_admin_user(session,actor_id,token,settings,clock)
  total=session.scalar(select(func.count()).select_from(User))
  rows=list(session.scalars(select(User).order_by(User.created_at.desc(),User.id.desc()).limit(limit).offset(offset)))
  fields=['id','email','name','role','verified','suspended','created_at']
  return {'items':[{key:getattr(user,key) for key in fields} for user in rows],'total':total,'count':len(rows),'limit':limit,'offset':offset}

def set_student_suspension(database,actor_id,token,target_id,suspended,settings,*,clock):
 with database.session() as session:
  locked={}
  for id in sorted({actor_id,target_id}):
   locked[id]=session.scalar(select(User).where(User.id==id).with_for_update())
  # All required account locks already belong to this transaction before rechecking.
  locked_admin_user(session,actor_id,token,settings,clock)
  target=locked[target_id]
  if target is None:raise AdminTargetUnavailable()
  if target_id==actor_id or target.role!='student':raise AdminTargetForbidden()
  target.suspended=suspended
  if suspended:revoke_user_sessions(session,target_id,clock())
  session.flush()
  result={'id':target_id,'suspended':target.suspended}
 return result
