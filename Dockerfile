FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY app ./app

# Single worker — Cloud Run scales horizontally, not vertically.
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
