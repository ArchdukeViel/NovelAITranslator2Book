FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN python -m pip install --upgrade pip

COPY pyproject.toml readme.md ./
COPY backend ./backend

RUN python -m pip install --no-cache-dir ".[documents,openai,gemini]"

ENV WEB_HOST=0.0.0.0
ENV WEB_PORT=8000
ENV NOVEL_LIBRARY_DIR=/app/storage/novel_library

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "novelai.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
