FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WATCH_ENABLED=false

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY CLAUDE.md README.md .env.example /app/

EXPOSE 8000

CMD ["uvicorn", "app.server:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
