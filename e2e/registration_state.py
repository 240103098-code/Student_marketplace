"""Mounted only in an owned disposable app; fixed read-only registration predicates."""
import json
import hashlib
import os
from pathlib import Path
import re
import sys
import psycopg
from argon2 import PasswordHasher


def main():
    request=json.load(sys.stdin)
    if set(request)!={'email','password','operation'}:raise ValueError()
    email,password,operation=(request[k] for k in ('email','password','operation'))
    prefix=os.environ['E2E_ID_PREFIX']
    if not re.fullmatch(r'e2e-[a-f0-9]{32}-',prefix) or operation not in ('snapshot','compare'):raise ValueError()
    if not isinstance(email,str) or not re.fullmatch(re.escape(prefix)+r'[a-z0-9-]{1,30}(?:@[^\s@]{1,100})?',email):raise ValueError()
    if not isinstance(password,str) or len(password)>129:raise ValueError()
    marker=Path('/tmp')/('registration-'+hashlib.sha256(email.encode()).hexdigest()+'.json')
    with psycopg.connect(os.environ['DATABASE_URL'].replace('postgresql+psycopg:','postgresql:'),options='-c default_transaction_read_only=on -c statement_timeout=5000') as connection:
        with connection.cursor() as cursor:
            cursor.execute('SELECT id,email,password_hash,verified,suspended,role FROM users WHERE email=%s',(email,));users=cursor.fetchall()
            cursor.execute('SELECT c.* FROM email_codes c JOIN users u ON u.id=c.user_id WHERE u.email=%s ORDER BY c.id',(email,));codes=cursor.fetchall()
            cursor.execute('SELECT count(*) FROM refresh_sessions r JOIN users u ON u.id=r.user_id WHERE u.email=%s',(email,));sessions=cursor.fetchone()[0]
    state=hashlib.sha256(json.dumps([users,codes,sessions],default=str).encode()).hexdigest()
    unchanged=operation=='compare' and marker.exists() and marker.read_text()==state
    if operation=='snapshot':marker.write_text(state)
    stored=False
    if len(users)==1:
        try:stored=users[0][2].startswith('$argon2id$') and users[0][2]!=password and PasswordHasher().verify(users[0][2],password)
        except Exception:pass
    print(json.dumps({'users':len(users),'codes':len(codes),'sessions':sessions,'unverified_student':len(users)==1 and users[0][3:]==(False,False,'student'),'registration_code':len(codes)==1 and codes[0][2]=='registration','one_way_password':stored,'unchanged':unchanged}))

if __name__=='__main__':
    try:main()
    except Exception:raise SystemExit(1)
