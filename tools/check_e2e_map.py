"""Check the exact canonical business-operation map; no runtime or .env read."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def validate():
    schema=json.loads((ROOT/'openapi.yml').read_text())
    expected={(method.upper(),path) for path, methods in schema['paths'].items() for method in methods if method in {'get','post','patch','put','delete','options','head'}}
    rows=json.loads((ROOT/'e2e/operation-map.json').read_text())
    actual={(row['method'],row['path']) for row in rows}
    assert len(expected)==len(actual)==len(rows)==40
    assert actual==expected
    assert {row['issue'] for row in rows}|{85}==set(range(61,86))
    assert all(row['status'] in {'smoke-only','planned'} and row['planned_spec']==f"e2e/features/issue-{row['issue']}.spec.cjs" and row['cross_cutting_issue']==85 for row in rows)
    return rows
if __name__=='__main__':
    validate();print('PASS exact 40 canonical operations map to 25 future issues; no feature completion claimed.')
