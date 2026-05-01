from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from pocketStudio.api import agents, chat, compat, messages, system, tasks, teams
from pocketStudio.core.config import get_settings
from pocketStudio.core.dependencies import get_database, get_worker_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_database().initialize()
    settings = get_settings()
    worker = get_worker_service()
    if settings.worker_enabled:
        worker.start()
    yield
    await worker.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    static_dir = Path(__file__).parent / "static"
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    def office() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    app.include_router(system.router, prefix=settings.api_prefix)
    app.include_router(compat.router, prefix=settings.api_prefix)
    app.include_router(agents.router, prefix=settings.api_prefix)
    app.include_router(teams.router, prefix=settings.api_prefix)
    app.include_router(messages.router, prefix=settings.api_prefix)
    app.include_router(chat.router, prefix=settings.api_prefix)
    app.include_router(tasks.router, prefix=settings.api_prefix)
    return app


app = create_app()
