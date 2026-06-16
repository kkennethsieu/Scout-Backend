FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

ENV PORT=8080
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1