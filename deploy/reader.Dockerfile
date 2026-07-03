FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN python -m pip install --upgrade pip

COPY pyproject.toml readme.md ./
COPY backend ./backend
COPY backend/src/novelai_shared ./backend/src/novelai_shared

RUN python -m pip install --no-cache-dir ".[documents,openai,gemini,db,worker,auth]"
RUN python -m pip install --no-cache-dir -e ./backend/src/novelai_shared

ENV WEB_HOST=0.0.0.0
ENV WEB_PORT=8001
ENV NOVEL_LIBRARY_DIR=/app/storage/novel_library

EXPOSE 8001

CMD ["python", "-m", "uvicorn", "novelai.main_reader:app", "--host", "0.0.0.0", "--port", "8001"]
