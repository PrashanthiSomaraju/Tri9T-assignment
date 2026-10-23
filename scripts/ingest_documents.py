import argparse
import json
from pathlib import Path
from app.core.config import Settings
from app.core.database import Base,database
from app.services.ingestion import ingest
from app.models import generation,selection


def main():
    p=argparse.ArgumentParser();p.add_argument('pdf',type=Path);p.add_argument('--document-key',default='ct200')
    args=p.parse_args();engine,sessions=database(Settings().database_url)
    Base.metadata.create_all(engine)
    with sessions() as session:
        version,duplicate=ingest(session,args.pdf.read_bytes(),args.pdf.name,args.document_key)
        print(json.dumps({'document_id':version.document_id,'version':version.version_number,'duplicate':duplicate,'warnings':version.report['warnings']},indent=2))
    engine.dispose()


if __name__=='__main__': main()
