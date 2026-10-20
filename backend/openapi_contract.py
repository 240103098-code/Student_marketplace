"""Documentation-only enrichment for manual Request parsers; never runtime validation.

Installed on the actual app, so /openapi.json and the deterministic export agree.
Unsupported methods/paths are never added. Cross-field/normalization/security rules
that JSON Schema cannot enforce are documented with descriptions/x-* metadata.
"""
from copy import deepcopy
from fastapi.openapi.utils import get_openapi
from backend.schemas import DeleteAccountRequest
from backend.listing_schemas import ListingCreateRequest, ListingEditRequest, ListingReportRequest
from backend.admin_schemas import SuspensionRequest, ListingRejectionRequest
from backend.images import MAX_BYTES, MAX_PIXELS, FORM_LIMIT
from backend.tokens import ISSUER, AUDIENCE

MAX_ID=9223372036854775807
ID={'type':'integer','format':'int64','minimum':1,'maximum':MAX_ID}
DATE={'type':'string','format':'date-time'}
NULL_DATE={'anyOf':[DATE,{'type':'null'}]}
STATES=['pending','active','sold','rejected','removed']
PRICE_TEXT=r'^(?:(?:0|[1-9][0-9]{0,8})(?:\.[0-9]{1,2}0*)?|1000000000(?:\.0+)?)$'
PRICE_INPUT={'anyOf':[{'type':'string','pattern':PRICE_TEXT},{'type':'number','minimum':0,'maximum':1000000000,'multipleOf':0.01}], 'description':'Exact finite KZT amount0..1000000000; at most two meaningful fractional digits; trailing fractional zeros allowed. JSON numbers are parsed as Decimal, never rounded from binary float.'}
PRICE_OUTPUT={'type':'string','pattern':r'^(?:(?:0|[1-9][0-9]{0,8})\.[0-9]{2}|1000000000\.00)$','description':'Canonical nonnegative KZT amount with exactly two decimal places.'}

def obj(properties,**extra):return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False,**extra}
def ref(name):return {'$ref':'#/components/schemas/'+name}
def json_content(schema):return {'application/json':{'schema':schema}}
def body(schema,required=True,**extra):return {'required':required,'content':json_content(schema),**extra}
def header(description,schema=None):return {'description':description,'schema':schema or {'type':'string'}}
def parameter(name,location,schema,required=False,description=''):
 return {'name':name,'in':location,'required':required,'schema':schema,'description':description}

MANUAL_BODIES={
 ('/listings','post'):ListingCreateRequest,
 ('/listings/{listing_id}','patch'):ListingEditRequest,
 ('/listings/{listing_id}/reports','post'):ListingReportRequest,
 ('/users/me','delete'):DeleteAccountRequest,
 ('/admin/users/{target_id}/suspension','patch'):SuspensionRequest,
 ('/admin/listings/{listing_id}/reject','post'):ListingRejectionRequest,
}
MANUAL_RESULTS={
 ('/auth/verify-email','post'):('200','VerifiedResult'),
 ('/auth/resend-verification','post'):('202','AcceptedMessage'),
 ('/auth/forgot-password','post'):('202','AcceptedMessage'),
 ('/auth/csrf','get'):('200','CsrfResult'),
 ('/admin/me','get'):('200','AdminIdentity'),
 ('/users/me/avatar','post'):('200','AvatarResult'),
 ('/users/me/avatar','delete'):('200','AvatarResult'),
 ('/users/me','delete'):('200','AccountDeleted'),
 ('/categories','get'):('200','Categories'),
 ('/listings/{listing_id}/photos','post'):('201','CreatedPhoto'),
 ('/listings/{listing_id}/sold','post'):('200','SoldResult'),
 ('/listings/{listing_id}','delete'):('200','ListingDeleted'),
 ('/listings/{listing_id}/reports','post'):('202','ReportAccepted'),
 ('/admin/users/{target_id}/suspension','patch'):('200','SuspensionResult'),
 ('/admin/listings/{listing_id}/remove','post'):('200','RemovedResult'),
 ('/admin/listings/{listing_id}/approve','post'):('200','ApprovedResult'),
 ('/admin/listings/{listing_id}/reject','post'):('200','RejectedResult'),
 ('/admin/reports/{report_id}/review','post'):('200','ReviewedResult'),
}
ACTIONS={('/listings/{listing_id}/sold','post'),('/listings/{listing_id}','delete'),('/admin/listings/{listing_id}/remove','post'),('/admin/listings/{listing_id}/approve','post'),('/admin/reports/{report_id}/review','post')}
UPLOADS={'/users/me/avatar','/listings/{listing_id}/photos'}
BINARIES={'/users/me/avatar','/listings/{listing_id}/photos/{photo_id}','/admin/listings/{listing_id}/photos/{photo_id}'}
PAGES={'/listings','/listings/mine','/admin/users','/admin/listings','/admin/reports'}
RATE={('/auth/register','post'),('/auth/login','post'),('/auth/resend-verification','post'),('/auth/forgot-password','post'),('/auth/refresh','post'),('/listings','post'),('/listings/{listing_id}/reports','post'),('/users/me/avatar','post'),('/listings/{listing_id}/photos','post')}
COOKIE_SET={('/auth/login','post'),('/auth/refresh','post'),('/auth/logout','post'),('/auth/change-password','post'),('/auth/reset-password','post'),('/users/me','delete')}

# Only additional handled statuses; common transport/validation/database failures below.
ERRORS={
 ('/auth/register','post'):{409,503},('/auth/verify-email','post'):{400},('/auth/resend-verification','post'):{503},('/auth/login','post'):{401,403},('/auth/csrf','get'):{401,403},('/auth/refresh','post'):{401,403},('/auth/logout','post'):{403},('/auth/change-password','post'):{400},('/auth/reset-password','post'):{400},
 ('/users/me','delete'):{400},('/users/me/avatar','get'):{404},('/users/me/avatar','post'):{400,413},
 ('/listings','post'):{400},('/listings/{listing_id}','get'):{404},('/listings/{listing_id}/edit','get'):{404},('/listings/{listing_id}','patch'):{404,409},('/listings/{listing_id}','delete'):{404},('/listings/{listing_id}/sold','post'):{404,409},('/listings/{listing_id}/reports','post'):{400,404},('/listings/{listing_id}/photos','post'):{400,404,409,413},('/listings/{listing_id}/photos/{photo_id}','get'):{404},
 ('/admin/users/{target_id}/suspension','patch'):{400,404},('/admin/listings/{listing_id}','get'):{404},('/admin/listings/{listing_id}/photos/{photo_id}','get'):{404},('/admin/listings/{listing_id}/remove','post'):{404},('/admin/listings/{listing_id}/approve','post'):{404,409},('/admin/listings/{listing_id}/reject','post'):{404,409},('/admin/reports/{report_id}/review','post'):{404},
}

POLICIES={
 ('/listings','get'):{'visible_states':['active'],'published_required':True,'seller':'currently verified and unsuspended'},
 ('/listings/{listing_id}','get'):{'visible_states':['active'],'published_required':True,'seller':'currently verified and unsuspended','owner_bypass':False},
 ('/listings/mine','get'):{'owner_only':True,'states':STATES,'removed_photos':[]},
 ('/listings','post'):{'owner':'current account','contact_required':True,'server_state':'pending','published_at':None},
 ('/listings/{listing_id}/edit','get'):{'owner_only':True,'states':STATES},
 ('/listings/{listing_id}','patch'):{'owner_only':True,'states':['pending','active','sold'],'mutable_fields':['price','description'],'approval_and_photos':'preserved'},
 ('/listings/{listing_id}','delete'):{'owner_only':True,'states':STATES,'hard_delete':True,'file_cleanup':'after committed deletion; cleanup_pending may be true'},
 ('/listings/{listing_id}/sold','post'):{'owner_only':True,'from':['active','sold'],'to':'sold','idempotent':True},
 ('/listings/{listing_id}/photos','post'):{'owner_only':True,'states':['pending'],'maximum_photos':5},
 ('/listings/{listing_id}/photos/{photo_id}','get'):{'linked_photo_required':True,'owner_states':['pending','active','sold','rejected'],'other_viewer':'Active/published listing and currently eligible seller; Removed hidden'},
 ('/listings/{listing_id}/reports','post'):{'visible_states':['active'],'self_report':False,'duplicate':'accepted no-op, first reason retained','listing_action':'none'},
 ('/admin/users/{target_id}/suspension','patch'):{'target':'other student only, never self/admin','suspend':'atomically revoke all sessions and hide seller listings without changing listing states','unsuspend':'does not restore verification or sessions'},
 ('/admin/listings/{listing_id}/photos/{photo_id}','get'):{'linked_photo_required':True,'states':STATES,'removed':'retained private admin review only'},
 ('/admin/listings/{listing_id}/remove','post'):{'states':STATES,'to':'removed','idempotent':True,'records_photos_reports':'retained'},
 ('/admin/listings/{listing_id}/approve','post'):{'from':['pending','active'],'to':'active','seller':'currently verified and unsuspended','publication':'first trusted timestamp retained on idempotent Active retry'},
 ('/admin/listings/{listing_id}/reject','post'):{'from':['pending','rejected'],'to':'rejected','retry':'only identical normalized reason is idempotent','resurrection':False},
 ('/admin/reports/{report_id}/review','post'):{'idempotent':True,'timestamp':'first reviewed_at retained','listing_action':'none; Removed records can still be reviewed'},
 ('/auth/verify-email','post'):{'code':'six ASCII digits, ten-minute expiry, five persisted wrong attempts','success':'consume code and verify account; no automatic login/JWT'},
 ('/auth/change-password','post'):{'current_password_required':True,'success':'atomic password update and revoke all account session families, then clear refresh cookie'},
 ('/auth/reset-password','post'):{'purpose':'password-reset code only; verified unsuspended account','code':'six ASCII digits, ten-minute expiry, five persisted wrong attempts','success':'consume code, update password, revoke all sessions; no activation or JWT'},
}

def enrich(document):
 schemas=document.setdefault('components',{}).setdefault('schemas',{})
 manual={
  'SafeError':obj({'detail':{'type':'string'}},description='Handled safe error; never raw input, credentials or driver details.'),
  'VerifiedResult':obj({'verified':{'type':'boolean','const':True}}),
  'AcceptedMessage':obj({'detail':{'type':'string'}},description='Generic eligible-address guidance; no guarantee of delivery or account existence.'),
  'CsrfResult':obj({'csrf_token':{'type':'string','pattern':'^[0-9a-f]{64}$','readOnly':True}}),
  'AdminIdentity':obj({'id':ID,'is_admin':{'type':'boolean','const':True}}),
  'AvatarResult':obj({'detail':{'type':'string'},'cleanup_pending':{'type':'boolean'}}),
  'AccountDeleted':obj({'deleted':{'type':'boolean','const':True},'cleanup_pending':{'type':'boolean'}}),
  'ListingDeleted':obj({'id':ID,'deleted':{'type':'boolean','const':True},'cleanup_pending':{'type':'boolean'}}),
  'CreatedPhoto':obj({'id':ID,'listing_id':ID,'position':{'type':'integer','minimum':1,'maximum':5},'is_main':{'type':'boolean'},'url':{'type':'string','pattern':r'^/listings/[1-9][0-9]*/photos/[1-9][0-9]*$'}},description='Append ordinal1..5; first/lowest position is main; protected URL, no storage path.'),
  'SoldResult':obj({'id':ID,'status':{'const':'sold','type':'string'},'published_at':NULL_DATE}),
  'RemovedResult':obj({'id':ID,'status':{'const':'removed','type':'string'},'published_at':NULL_DATE}),
  'ApprovedResult':obj({'id':ID,'status':{'const':'active','type':'string'},'published_at':DATE,'rejection_reason':{'type':'null'}}),
  'RejectedResult':obj({'id':ID,'status':{'const':'rejected','type':'string'},'published_at':{'type':'null'},'rejection_reason':{'type':'string','minLength':1,'maxLength':300}}),
  'ReportAccepted':obj({'accepted':{'type':'boolean','const':True}}),
  'SuspensionResult':obj({'id':ID,'suspended':{'type':'boolean'}}),
  'ReviewedResult':obj({'id':ID,'reviewed_at':DATE},description='Idempotent: first review timestamp retained. Does not moderate listing.'),
  'EmptyAction':obj({},maxProperties=0,description='No body or bytes parsing as empty JSON object; content type is not consulted. No query parameters; nonempty payload rejected. Action parser caps bytes at1024.'),
 }
 labels=['Electronics','Clothing','Books','Furniture','Other']
 manual['Categories']={'type':'array','minItems':5,'maxItems':5,'uniqueItems':True,'items':{'oneOf':[obj({'id':{'const':i,'type':'integer'},'key':{'const':label.lower(),'type':'string'},'label':{'const':label,'type':'string'}}) for i,label in enumerate(labels,1)]},'description':'Fixed categories, ordered by numeric id1..5.'}
 for model in MANUAL_BODIES.values():schemas.setdefault(model.__name__,model.model_json_schema(ref_template='#/components/schemas/{model}'))
 schemas.update(deepcopy(manual))
 # Align generated Pydantic schemas with validators/serializers without changing them.
 requests={name for name in schemas if name.endswith('Request')}|{'ProfilePatch'}
 for name,schema in schemas.items():
  props=schema.get('properties',{})
  if name in requests:schema['additionalProperties']=False
  for key,value in props.items():
   if key in {'id','listing_id','target_id','photo_id','report_id'}:value.update(deepcopy(ID))
   if key=='category_id':value.update(type='integer',enum=[1,2,3,4,5])
   if key=='price':props[key]=deepcopy(PRICE_INPUT if name in requests else PRICE_OUTPUT)
   if key=='code':value.update(pattern='^[0-9]{6}$',writeOnly=True)
   if key in {'password','new_password','current_password'}:value.update(writeOnly=True,description='12..128 characters; never trimmed, echoed or stored in plaintext.')
   if key=='email':
    if name in requests:
     value.pop('maxLength',None);value.update(description='Trim/lowercase before validation. Exact ASCII sdu.edu.kz domain, valid non-SMTPUTF8 email, normalized maximum254 characters; no DNS request.',**{'x-normalized-maxLength':254,'x-university-domain':'sdu.edu.kz'})
    else:value.update(format='email',maxLength=254)
   if key in {'title','description','reason'} and name in {'ListingCreateRequest','ListingEditRequest','ListingRejectionRequest'}:
    maximum=value.pop('maxLength',None);value.pop('default',None)
    if maximum:value['x-normalized-maxLength']=maximum
    value['description']='Trim before length validation; no NUL. Bounds apply after trimming.';value['x-normalized-minLength']=value.get('minLength',1);value['pattern']='^[^'+chr(92)+'u0000]*$'
  if name not in requests and 'properties' in schema:schema['additionalProperties']=False;schema['required']=list(props)
  if 'limit' in props:props['limit'].update(minimum=1,maximum=50)
  for key in ['total','count','offset']:
   if key in props:props[key].update(minimum=0)
  if 'photos' in props:props['photos'].update(maxItems=5)
  if name=='AccessTokenResponse':props['expires_in'].update(minimum=1,default=900,description='Seconds; default configured JWT_ACCESS_MINUTES15 gives900. Frontend boundary uses that default.');props['access_token'].update(minLength=1,readOnly=True)
 for name in ['AuthMeResponse','ProfileResponse']:
  if name in schemas:schemas[name]['properties']['verified'].update(const=True)
 if 'RegistrationResponse' in schemas:schemas['RegistrationResponse']['properties']['verified'].update(const=False)
 if 'ListingEditRequest' in schemas:
  schemas['ListingEditRequest']['minProperties']=1
  schemas['ListingEditRequest']['properties']['description']={'type':'string','minLength':10,'x-normalized-maxLength':2000,'pattern':'^[^'+chr(92)+'u0000]*$','description':'Trimmed10..2000 characters, no NUL; optional but explicit null is rejected.'}
 profile=schemas['ProfilePatch'];profile['minProperties']=1
 profile['properties']['name']={'type':'string','minLength':1,'x-normalized-maxLength':100,'description':'Optional; trim first, require nonblank1..100 characters. Explicit null rejected. Omitted fields preserved.'}
 for field,pattern in [('phone',r'^\+[0-9]{7,15}$'),('telegram_username',r'^[A-Za-z0-9_]{5,32}$')]:
  profile['properties'][field]={'anyOf':[{'type':'string','pattern':pattern},{'type':'null'}],'description':'Null clears; omission preserves.'}
 profile['properties']['external_contact_url']={'anyOf':[{'type':'string','maxLength':2048,'pattern':r'^[Hh][Tt][Tt][Pp][Ss]://[^\s]+$'},{'type':'null'}],'description':'HTTPS URL with valid host/port, no credentials/whitespace/control characters. Null clears; omission preserves. Host validation also runs server-side.'}
 schemes=document['components'].setdefault('securitySchemes',{})
 schemes['HTTPBearer']={'type':'http','scheme':'bearer','bearerFormat':'JWT','description':f'HS256 access JWT; issuer {ISSUER}, audience {AUDIENCE}, type access, required iss/aud/sub/type/iat/exp/jti/sid. Default lifetime900s. Every request reloads current verified/unsuspended account and live refresh family; token role flags never grant authority.'}
 schemes['RefreshCookie']={'type':'apiKey','in':'cookie','name':'refresh_token','description':'Opaque64-character refresh token. HttpOnly; host-only; Path=/auth; SameSite=Lax; Secure in production. Fixed family expiry default7days, rotation never extends it. Browser sends credentials; replay revokes family.'}
 schemes['CsrfHeader']={'type':'apiKey','in':'header','name':'X-CSRF-Token','description':'64 lowercase hex characters bound to refresh family, obtained from GET/auth/csrf. Allowed Origin also required on refresh/logout; OpenAPI does not enforce these rules.'}
 for path,methods in document['paths'].items():
  for method,operation in methods.items():
   if method not in {'get','post','patch','delete'}:continue
   key=(path,method);has_validation='422' in operation['responses'] or key in MANUAL_BODIES or key in ACTIONS or path in PAGES and method=='get';protected=not path.startswith('/auth/') or path in {'/auth/me','/auth/change-password'}
   operation['x-contract-source']='Existing runtime parser/DTO; documentation only.'
   if key in POLICIES:operation['x-workflow-policy']=deepcopy(POLICIES[key])
   operation['x-authorization']='Current verified unsuspended account + live session family'+('; current database admin role required' if path.startswith('/admin/') else '') if protected else 'Public or refresh-cookie endpoint; see security/parameters.'
   if protected:operation['security']=[{'HTTPBearer':[]}]
   parameters=operation.setdefault('parameters',[])
   for item in parameters:
    if item.get('in')=='path':item['schema'].update(deepcopy(ID))
   if path in PAGES and method=='get':
    for field,default,minimum,maximum in [('limit',20,1,50),('offset',0,0,MAX_ID)]:parameters.append(parameter(field,'query',{'type':'integer','minimum':minimum,'maximum':maximum,'default':default,'x-wire-pattern':r'^(?:0|[1-9][0-9]*)$'},description='Canonical unsigned decimal digits only, no signs/leading zeros/exponents.'))
    if path in {'/listings/mine','/admin/listings'}:parameters.append(parameter('status','query',{'type':'string','enum':STATES},description='Omit for all states; empty value rejected.'))
    if path=='/admin/reports':parameters.append(parameter('state','query',{'type':'string','enum':['unreviewed','reviewed','all'],'default':'unreviewed'}))
    if path=='/listings':
     parameters.extend([parameter('q','query',{'type':'string','maxLength':200},description='Trim; blank means no search. Case-insensitive literal substring in title OR description. Control characters rejected; percent/underscore/backslash are literal.'),parameter('category_id','query',{'type':'integer','enum':[1,2,3,4,5]},description='Single canonical numeric id, no aliases/leading zeros.'),parameter('condition','query',{'type':'string','enum':['new','used']})])
     for field in ['min_price','max_price']:parameters.append(parameter(field,'query',{'type':'string','pattern':PRICE_TEXT},description='Inclusive exact KZT bound0..1b; at most two meaningful fractional digits; min<=max, no whitespace/sign/exponent/empty value.'))
    operation['x-strict-query']={'unknown':'rejected','duplicate':'rejected','cross-field':'min_price must not exceed max_price' if path=='/listings' else None}
   if key in MANUAL_BODIES:
    operation['requestBody']=body(ref(MANUAL_BODIES[key].__name__))
    operation['x-json-parser']={'duplicate-fields':'rejected','nonfinite':'rejected','maxBytes':65536,'contentType':'application/json'}
   if key in ACTIONS:
    operation['requestBody']={'required':False,'content':{'application/json':{'schema':ref('EmptyAction')},'*/*':{'schema':ref('EmptyAction')}}}
    operation['x-strict-query']={'unknown':'rejected','duplicate':'rejected'}
   if key in {('/users/me','delete'),('/admin/users/{target_id}/suspension','patch'),('/admin/listings/{listing_id}/reject','post'),('/listings/{listing_id}/reports','post')}:operation['x-strict-query']={'unknown':'rejected','duplicate':'rejected'}
   if path in UPLOADS and method=='post':
    operation['requestBody']={'required':True,'content':{'multipart/form-data':{'schema':obj({'image':{'type':'string','format':'binary','description':'Exactly one decoded JPEG/PNG/WebP file; maximum5MiB and20million pixels.'}},**{'x-max-file-bytes':MAX_BYTES,'x-max-pixels':MAX_PIXELS,'x-max-multipart-bytes':FORM_LIMIT})}}}
    operation['description']=(operation.get('description','')+' Exactly one image file; no extra fields/files. Bounded streaming parser and MIME-by-decoding validation; original metadata stripped. Owner listing uploads require Pending and at most five photos.').strip()
   if path in {'/auth/login','/auth/csrf','/auth/refresh','/auth/logout'}:
    required=path in {'/auth/refresh','/auth/logout'}
    parameters.append(parameter('Origin','header',{'type':'string'},required,description='Must exactly match configured frontend origin. Required for refresh/logout; login/CSRF reject an invalid supplied origin.'))
   if path in {'/auth/csrf','/auth/refresh'}:operation['security']=[{'RefreshCookie':[],**({'CsrfHeader':[]} if path=='/auth/refresh' else {})}]
   if path=='/auth/logout':operation['security']=[{'CsrfHeader':[]}];parameters.append(parameter('refresh_token','cookie',{'type':'string'},description='Optional: absent/unknown session is idempotent; known family requires matching CSRF.'))
   if path in {'/auth/refresh','/auth/logout'}:
    parameters.append(parameter('X-CSRF-Token','header',{'type':'string','pattern':'^[0-9a-f]{64}$'},True,'Must match the cookie family, except state-free logout of absent/unknown cookie.'))
    operation['x-request-body-behavior']='No payload used; these routes ignore fields after global64KiB streamed cap (unlike strict listing/admin actions).'
   if key in MANUAL_RESULTS:
    status,name=MANUAL_RESULTS[key];operation['responses'][status]={'description':'Success','content':json_content(ref(name))}
   if path in BINARIES and method=='get':operation['responses']['200']={'description':'Authorized private decoded image; no raw storage paths or query tokens. Owner/admin/buyer state visibility rechecked.','content':{mime:{'schema':{'type':'string','format':'binary'}} for mime in ['image/jpeg','image/png','image/webp']}}
   errors=set(ERRORS.get(key,set()))|{500,503}
   if protected:errors.add(401)
   if path.startswith('/admin/'):errors.add(403)
   if has_validation:errors.add(422)
   if method in {'post','patch','delete'}:
    errors.add(400)
    errors.add(422 if path.startswith('/listings') else 413)
   if key in RATE:errors.add(429)
   busy_description='Bounded SQLite writer wait exhausted; safe failure with no automatic mutation replay.'
   if key==('/auth/forgot-password','post'):busy_description+=' Recovery SMTP delivery failures still return generic 202.'
   if key in {('/auth/register','post'),('/auth/resend-verification','post')}:busy_description='Configured verification email transport unavailable or '+busy_description
   for status in sorted(errors):operation['responses'][str(status)]={'description':{400:'Invalid code/current password/action/image or interrupted transport.',401:'Missing/invalid/expired/revoked session or ineligible account; safe generic error.',403:'Current admin access denied, or invalid required/supplied Origin/CSRF where applicable.',404:'Missing, unlinked, unauthorized or invisible resource.',409:'Duplicate account or conflicting listing/publication state.',413:'Streamed request/file exceeds its bound.',422:'Strict payload/query/path validation failed; detail-only safe error.',429:'Rate window/capacity exceeded; no action performed by this request.',500:'Handled database/storage failure, sanitized.',503:busy_description}[status], 'content':json_content(ref('SafeError'))}
   for status,response in operation['responses'].items():
    headers=response.setdefault('headers',{})
    headers['Cache-Control']=header('All handled sensitive responses are private, no-store.',{'type':'string','const':'private, no-store'})
    headers['X-Content-Type-Options']=header('Disable MIME sniffing.',{'type':'string','const':'nosniff'})
    if status=='503':headers['Retry-After']=header('Present for bounded SQLite writer contention; SMTP failure need not supply it.',{'type':'integer','const':1})
    if status=='401':headers['WWW-Authenticate']=header('Bearer challenge.',{'type':'string','const':'Bearer'})
    if status=='429' or status=='202' and path in {'/auth/resend-verification','/auth/forgot-password'}:headers['Retry-After']=header('Seconds before retry; generic mail guidance60.',{'type':'integer','minimum':1,**({'const':60} if status=='202' else {})})
    if key in COOKIE_SET and status.startswith('2'):headers['Set-Cookie']=header('Sets/rotates refresh_token on login/refresh; clears it on logout/password change/reset/account deletion. HttpOnly; host-only; Path=/auth; SameSite=Lax; Secure required in production.')
    if status=='204':response.pop('content',None)
   if not parameters:operation.pop('parameters',None)
 for unused in ['HTTPValidationError','ValidationError']:schemas.pop(unused,None)
 document['info']['description']='Canonical working Student Marketplace API. Generated from the actual app plus documentation-only metadata for manual Request parsers. OpenAPI describes, but does not enforce, current account/role/state/CSRF/normalization/duplicate/size rules. Exact configured credentialed CORS origins; no wildcard; framework preflight handled by middleware. This contract adds no backend/provider/storage endpoints.'
 return document

def install_contract(app):
 def canonical_openapi():
  if app.openapi_schema is None:app.openapi_schema=enrich(get_openapi(title=app.title,version=app.version,description=app.description,routes=app.routes))
  return app.openapi_schema
 app.openapi=canonical_openapi
