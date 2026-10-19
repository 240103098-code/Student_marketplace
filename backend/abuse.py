"""Bounded process-local fixed windows; no submitted identities are retained."""
from dataclasses import dataclass
import hashlib
import hmac
import math
import secrets
from threading import Lock
from fastapi import HTTPException

@dataclass
class Counter:
 expires:float
 count:int=0

class RateLimited(Exception):
 def __init__(self,retry):self.retry=max(1,int(retry))

class Limiter:
 def __init__(self,clock,capacity=10000):
  if type(capacity) is not int or capacity<1:raise ValueError('Invalid limiter capacity')
  self.clock=clock;self.capacity=capacity;self._entries={};self._lock=Lock();self._salt=secrets.token_bytes(32)
 def key(self,scope,identity):
  return hmac.new(self._salt,(scope+'\0'+str(identity)).encode(),hashlib.sha256).digest()
 def take(self,*rules):
  # Every rule is checked before any increment: composite email/IP quotas are atomic.
  with self._lock:
   now=self.clock().timestamp()
   for key in [key for key,value in self._entries.items() if value.expires<=now]:del self._entries[key]
   prepared=[(self.key(scope,identity),limit,window) for scope,identity,limit,window in rules]
   blocked=[math.ceil(self._entries[key].expires-now) for key,limit,window in prepared if key in self._entries and self._entries[key].count>=limit]
   if blocked:raise RateLimited(max(blocked))
   if len(self._entries)+len({key for key,_,_ in prepared if key not in self._entries})>self.capacity:raise RateLimited(60)
   reservations=[]
   for key,limit,window in prepared:
    entry=self._entries.setdefault(key,Counter(now+window));entry.count+=1;reservations.append((key,entry))
   return reservations
 def refund(self,reservations):
  with self._lock:
   for key,entry in reservations:
    if self._entries.get(key) is entry:
     entry.count-=1
     if entry.count==0:del self._entries[key]


def quota(request,*rules):
 try:return request.app.state.limiter.take(*rules)
 except RateLimited as error:raise HTTPException(status_code=429,detail='Too many requests. Retry later; no action was performed.',headers={'Retry-After':str(error.retry)}) from None


def peer(request):return request.client.host if request.client else 'unknown-peer'


def email_quota(request,email):quota(request,('email',email,5,3600))


def user_quota(request,user,scope,limit):quota(request,(scope,user.id,limit,3600))
