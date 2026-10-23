import json
import os
import tempfile
from pathlib import Path
from uuid import UUID


class GenerationStore:
    def __init__(self, directory: Path):
        self.directory=directory
        directory.mkdir(parents=True,exist_ok=True)

    def path(self, identifier: str):
        return self.directory / f'{UUID(identifier)}.json'

    def write(self, identifier: str, content: dict):
        path=self.path(identifier)
        fd,temp=tempfile.mkstemp(prefix='.generation-',dir=self.directory)
        try:
            with os.fdopen(fd,'w') as stream:
                json.dump(content,stream,ensure_ascii=False,indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp,path)
            directory_fd=os.open(self.directory,os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
        return str(path)

    def read(self, identifier):
        return json.loads(self.path(identifier).read_text())
