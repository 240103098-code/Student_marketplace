"""Deterministic actual-app schema; no settings files, engines, SMTP or services."""
import argparse
import json
from pathlib import Path
from backend.app import create_app
from backend.config import Settings

ROOT=Path(__file__).resolve().parents[1]

def schema():
    settings=Settings(APP_ENV='test',DATABASE_URL='postgresql+psycopg://schema_only@127.0.0.1/schema_only',JWT_SECRET_KEY='schema-export-only-'+'x'*48)
    # create_app only stores the injected database; schema generation never uses it.
    app=create_app(settings,database=object(),sender=object())
    return app.openapi()

def rendered():
    return json.dumps(schema(),sort_keys=True,indent=2,ensure_ascii=False)+'\n'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    destination=ROOT/'openapi.yml'
    content=rendered()
    if args.check:
        if not destination.exists() or destination.read_text(encoding='utf-8')!=content:
            parser.exit(1,'OpenAPI drift: run python -m tools.export_openapi\n')
        print('PASS OpenAPI matches actual FastAPI app.')
    else:
        destination.write_text(content,encoding='utf-8',newline='\n')
        print('Exported openapi.yml (JSON-compatible YAML).')

if __name__=='__main__':main()
