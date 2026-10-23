from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.core.config import Settings
from app.core.database import Base, database
from app.core.errors import DomainError
from app.api import documents, selections, generations
from app.services.generation_store import GenerationStore


def create_app(settings:Settings|None=None,provider=None):
    settings=settings or Settings()
    engine,sessions=database(settings.database_url)

    @asynccontextmanager
    async def lifespan(app):
        Base.metadata.create_all(engine)
        yield
        engine.dispose()

    app=FastAPI(title='CT-200 Versioned Document Intelligence',version='0.1.0',lifespan=lifespan)
    app.state.settings=settings
    app.state.sessions=sessions
    app.state.engine=engine
    app.state.provider=provider
    app.state.store=GenerationStore(settings.generation_dir)
    @app.exception_handler(DomainError)
    async def domain_error(request:Request,exc:DomainError):
        return JSONResponse(status_code=exc.status,content={'detail':exc.detail})
    @app.get('/health')
    def health():
        from sqlalchemy import text
        with engine.connect() as connection:
            connection.execute(text('SELECT 1'))
        return {'status':'ok','provider':settings.provider}
    app.include_router(documents.router)
    app.include_router(selections.router)
    app.include_router(generations.router)
    return app


logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s %(message)s')
app=create_app()
