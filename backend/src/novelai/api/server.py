from __future__ import annotations

import multiprocessing
import os

import uvicorn

from novelai.api.app import app
from novelai.config.settings import settings

_ADMIN_PORT = 8000
_READER_PORT = 8001


def _run_admin(*, reload: bool = False) -> None:
    uvicorn.run(
        "novelai.main_admin:app",
        host=settings.WEB_HOST,
        port=_ADMIN_PORT,
        log_level=settings.LOG_LEVEL.lower(),
        reload=reload,
    )


def _run_reader(*, reload: bool = False) -> None:
    uvicorn.run(
        "novelai.main_reader:app",
        host=settings.WEB_HOST,
        port=_READER_PORT,
        log_level=settings.LOG_LEVEL.lower(),
        reload=reload,
    )


def main(*, reload: bool = False) -> None:
    deploy_mode = os.environ.get("DEPLOY_MODE", "monolith")
    if deploy_mode == "split":
        p_admin = multiprocessing.Process(target=_run_admin, kwargs={"reload": reload})
        p_reader = multiprocessing.Process(target=_run_reader, kwargs={"reload": reload})
        p_admin.start()
        p_reader.start()
        p_admin.join()
        p_reader.join()
    else:
        uvicorn.run(
            "novelai.api.app:app" if reload else app,
            host=settings.WEB_HOST,
            port=settings.WEB_PORT,
            log_level=settings.LOG_LEVEL.lower(),
            reload=reload,
        )


if __name__ == "__main__":
    main()
