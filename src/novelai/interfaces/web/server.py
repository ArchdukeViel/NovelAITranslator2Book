from __future__ import annotations

import uvicorn

from novelai.config.settings import settings
from novelai.interfaces.web.api import app


def main(*, reload: bool = False) -> None:
    uvicorn.run(
        "novelai.interfaces.web.api:app" if reload else app,
        host=settings.WEB_HOST,
        port=settings.WEB_PORT,
        log_level=settings.LOG_LEVEL.lower(),
        reload=reload,
    )


if __name__ == "__main__":
    main()
