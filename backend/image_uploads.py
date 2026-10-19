"""Bounded multipart parsing with explicit cleanup on every abort/error path."""
from fastapi import HTTPException
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException,MultiPartParser
from starlette.requests import ClientDisconnect
from backend.images import FORM_LIMIT,MAX_BYTES


async def read_image_upload(request):
 consumed=0
 async def bounded_stream():
  nonlocal consumed
  async for chunk in request.stream():
   consumed+=len(chunk)
   if consumed>FORM_LIMIT:raise MultiPartException('Image transport exceeds limit')
   yield chunk
 parser=MultiPartParser(request.headers,bounded_stream(),max_files=1,max_fields=0,max_part_size=MAX_BYTES+1)
 try:
  form=await parser.parse()
  fields=list(form.multi_items())
  if len(fields)!=1 or fields[0][0]!='image' or not isinstance(fields[0][1],UploadFile):raise HTTPException(status_code=400,detail='Submit exactly one image file.')
  raw=await fields[0][1].read(MAX_BYTES+1)
  if len(raw)>MAX_BYTES:raise HTTPException(status_code=413,detail='Image exceeds five MiB.')
  return raw
 except MultiPartException:
  raise HTTPException(status_code=413 if consumed>FORM_LIMIT else 400,detail='Image upload is invalid or exceeds its limit.') from None
 except (ClientDisconnect,ValueError):
  raise HTTPException(status_code=400,detail='Image upload was interrupted or malformed.') from None
 finally:
  # Starlette closes these on MultiPartException, but not ClientDisconnect/parser errors.
  # Explicit finally also closes partially allocated spooled files on cancellation.
  for handle in parser._files_to_close_on_error:handle.close()
