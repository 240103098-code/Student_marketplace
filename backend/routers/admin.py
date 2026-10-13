from fastapi import APIRouter,Depends
from backend.admin import require_admin_user
router=APIRouter(prefix='/admin',tags=['administration'])
@router.get('/me')
def admin_identity(user=Depends(require_admin_user)):return {'id':user.id,'is_admin':True}
