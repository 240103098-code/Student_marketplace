"""Stream actual JSON bytes before framework parsing, plus private response headers."""
import re
from starlette.responses import JSONResponse
from backend.abuse import RateLimited

class SecurityBoundary:
 def __init__(self,app,limiter):self.app=app;self.limiter=limiter
 async def __call__(self,scope,receive,send):
  if scope['type']!='http':return await self.app(scope,receive,send)
  async def secured(message):
   if message['type']=='http.response.start':
    headers=[(k,v) for k,v in message.get('headers',[]) if k.lower() not in {b'cache-control',b'x-content-type-options'}]
    message={**message,'headers':headers+[(b'cache-control',b'private, no-store'),(b'x-content-type-options',b'nosniff')]}
   await send(message)
  path=scope['path'];method=scope['method'];peer=(scope.get('client') or ('unknown-peer',))[0]
  rule={'/auth/register':('register-ip',10,3600),'/auth/forgot-password':('recovery-ip',10,3600),'/auth/refresh':('refresh-ip',60,60)}.get(path)
  if method=='POST' and rule:
   limiter=scope['app'].state.limiter if 'app' in scope else self.limiter
   try:limiter.take((rule[0],peer,rule[1],rule[2]))
   except RateLimited as error:
    return await JSONResponse({'detail':'Too many requests. Retry later; no action was performed.'},status_code=429,headers={'Retry-After':str(error.retry)})(scope,receive,secured)
  content_type=dict(scope.get('headers',[])).get(b'content-type',b'').split(b';')[0].strip().lower()
  image_route=method=='POST' and (path=='/users/me/avatar' or re.fullmatch(r'/listings/[1-9][0-9]*/photos',path))
  if method in {'POST','PATCH','DELETE','PUT'} and not (content_type==b'multipart/form-data' and image_route):
   body=bytearray()
   while True:
    message=await receive()
    if message['type']=='http.disconnect':return await JSONResponse({'detail':'Request body was interrupted.'},status_code=400)(scope,receive,secured)
    if message['type']!='http.request':continue
    chunk=message.get('body',b'')
    if len(body)+len(chunk)>65536:
     # Existing exact listing validators use 422; preserve that contract while auth bodies use 413.
     status=422 if path.startswith('/listings') else 413
     return await JSONResponse({'detail':'Request body exceeds 64 KiB.'},status_code=status)(scope,receive,secured)
    body.extend(chunk)
    if not message.get('more_body',False):break
   delivered=False
   async def bounded_receive():
    nonlocal delivered
    if delivered:return await receive()
    delivered=True
    return {'type':'http.request','body':bytes(body),'more_body':False}
   return await self.app(scope,bounded_receive,secured)
  return await self.app(scope,receive,secured)
