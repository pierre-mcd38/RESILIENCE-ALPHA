FROM python:3.12-slim

WORKDIR /app

RUN groupadd -r appgroup && useradd -r -g appgroup appuser && mkdir -p /app/data && chown -R appuser:appgroup /app/data

COPY services/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/ /app/services/
ENV PYTHONPATH=/app
ENV API_PORT=8001
ENV RESILIENCE_DB_PATH=/app/data/payments.sqlite3

USER appuser
EXPOSE 8001

HEALTHCHECK --interval=10s --timeout=3s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health')"

CMD ["gunicorn", "-b", "0.0.0.0:8001", "--workers", "1", "--threads", "8", "services.api.app:app"]
