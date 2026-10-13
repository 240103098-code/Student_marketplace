"""One-file bounded multipart reader shared by private image routes."""

from fastapi import HTTPException, Request
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.formparsers import MultiPartException

from backend.images import FORM_LIMIT, MAX_BYTES


async def read_image_upload(request):
    consumed = 0
    async def limited_receive():
        nonlocal consumed
        message = await request.receive()
        consumed += len(message.get('body', b''))
        if consumed > FORM_LIMIT:
            raise MultiPartException('Image upload exceeds the request limit')
        return message
    limited = Request(request.scope, limited_receive)
    try:
        async with limited.form(max_files=1, max_fields=0, max_part_size=MAX_BYTES+1) as form:
            fields = list(form.multi_items())
            if len(fields) != 1 or fields[0][0] != 'image' or not isinstance(fields[0][1], UploadFile):
                raise HTTPException(status_code=400, detail='Submit exactly one image file.')
            raw = await fields[0][1].read(MAX_BYTES+1)
            if len(raw) > MAX_BYTES:
                raise HTTPException(status_code=413, detail='Image exceeds five MiB.')
    except StarletteHTTPException as error:
        if error.detail == 'Image upload exceeds the request limit':
            raise HTTPException(status_code=413, detail='Image exceeds five MiB.') from None
        if error.status_code == 413:
            raise
        raise HTTPException(status_code=400, detail='Submit exactly one image file.') from None
    return raw
