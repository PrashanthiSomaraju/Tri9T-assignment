"""API-driven demo. A unique output directory prevents overwriting user databases."""
import argparse
import json
from pathlib import Path
from uuid import uuid4
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.main import create_app
from app.services.llm_service import MockProvider
from scripts.inspect_pdf import inspect
from scripts.validate_hierarchy import validate


def flatten(tree):
    return [item for n in tree for item in [n,*flatten(n['children'])]]


def run(v1:Path,v2:Path,output:Path,synthetic=False):
    output.mkdir(parents=True,exist_ok=False)
    for p in (v1,v2):
        inspect(p,output,synthetic)
        validation=validate(p.read_bytes(),reference=synthetic)
        (output/f'{p.stem}.validation.json').write_text(json.dumps(validation,indent=2))
        assert all(c['status']=='pass' for c in validation['checks']),validation
    settings=Settings(database_url=f'sqlite:///{(output/"demo.db").resolve()}',generation_dir=output/'generations',provider='mock',_env_file=None)
    result={'synthetic_fixture':synthetic,'original_pdfs_validated':not synthetic,'provider':'mock','output':str(output),'steps':[]}
    with TestClient(create_app(settings,MockProvider())) as client:
        def get(path,**kwargs):
            r=client.get(path,**kwargs);r.raise_for_status();return r.json()
        def post(path,**kwargs):
            r=client.post(path,**kwargs);r.raise_for_status();return r.json()
        a=post('/api/documents/ingest',files={'file':(v1.name,v1.read_bytes(),'application/pdf')},data={'document_key':'ct200'})
        document=a['document_id'];prefix=f'/api/documents/{document}'
        v1tree=get(prefix+'/tree?version=1');v1nodes={n['section_number']:n for n in flatten(v1tree)}
        result['v1_tree']=v1tree
        result['search']=get(f'/api/nodes/search?q=299&document_id={document}&version=1')
        assert result['search'],'Expected safety requirement missing'
        selected=[v1nodes[n]['id'] for n in ['2.1.1.1','3.2','4.1']]
        s=post('/api/selections',json={'name':'Safety demo','document_id':document,'version':1,'node_revision_ids':selected})
        pinned=get(f"/api/selections/{s['id']}")
        initial=post(f"/api/selections/{s['id']}/generate",json={})
        assert initial['generation']['status']=='success'
        assert all(t['status'] in ('current','review_required') for t in initial['staleness']['tests'])
        gid=initial['generation']['id']
        post('/api/documents/ingest',files={'file':(v2.name,v2.read_bytes(),'application/pdf')},data={'document_key':'ct200'})
        versions=get(prefix+'/versions');assert len(versions)==2
        result['v2_tree']=get(prefix+'/tree?version=2')
        after=get(f'/api/generations/{gid}')
        assert after['generation']==initial['generation']
        assert get(f"/api/selections/{s['id']}")==pinned
        statuses=[t['status'] for t in after['staleness']['tests']]
        assert statuses[:2]==['stale','stale'],statuses
        assert statuses[2] in ('current','review_required'),statuses
        result['diff']=get(f"/api/nodes/{v1nodes['2.1.1.1']['logical_node_id']}/diff?from_version=1&to_version=2")
        result['generation_before']=initial;result['generation_after']=after
        b={n['section_number']:n for n in flatten(result['v2_tree'])}
        result['added_sections']=[n for n in b if n not in v1nodes]
        result['changed_sections']=[n for n in b if n in v1nodes and b[n]['content_hash']!=v1nodes[n]['content_hash']]
        result['steps']=['v1 ingested','tree browsed','safety search passed','selection pinned','mock generation validated','v2 ingested','both versions retained','historical output unchanged','selection unchanged','stale and unchanged cases verified','diff retrieved']
    (output/'demo.json').write_text(json.dumps(result,indent=2,ensure_ascii=False))
    summary=['# API demonstration',f'Synthetic fixtures: {synthetic}','Original manuals absent/unverified.' if synthetic else 'Original files supplied; inspect reports and visually review suspicious regions.',f'Test statuses after v2: {statuses}',f'Changed sections: {result["changed_sections"]}',f'Added sections: {result["added_sections"]}']+['PASS: '+s for s in result['steps']]
    (output/'demo.md').write_text('\n'.join(summary)+'\n')
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--synthetic',action='store_true');p.add_argument('--v1',type=Path,default=Path('data/ct200_manual.pdf'));p.add_argument('--v2',type=Path,default=Path('data/ct200_manual_v2.pdf'));p.add_argument('--output',type=Path)
    args=p.parse_args()
    output=args.output or Path('generated')/f'demo-{uuid4().hex[:8]}'
    if args.synthetic:
        from tests.fixtures.pdf_factory import make_pdf
        fixtures=Path('generated/synthetic');fixtures.mkdir(parents=True,exist_ok=True)
        args.v1=fixtures/'synthetic_v1.pdf';args.v2=fixtures/'synthetic_v2.pdf'
        args.v1.write_bytes(make_pdf(1));args.v2.write_bytes(make_pdf(2))
    for path in (args.v1,args.v2):
        if not path.exists():
            p.error(f'Original PDF missing: {path}. Supply originals, or explicitly use --synthetic.')
    result=run(args.v1,args.v2,output,args.synthetic)
    print(json.dumps({'output':str(output),'steps':result['steps'],'statuses':[t['status'] for t in result['generation_after']['staleness']['tests']]}))


if __name__=='__main__': main()
