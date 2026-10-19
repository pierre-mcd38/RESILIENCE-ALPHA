FROM python:3.12-slim

WORKDIR /app

RUN groupadd -r appgroup && useradd -r -g appgroup appuser && mkdir -p /app/data && chown -R appuser:appgroup /app/data

COPY services/executor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/executor /app/services/executor
ENV PYTHONPATH=/app
ENV EXECUTOR_PORT=8005
ENV EXECUTOR_AUDIT_PATH=/app/data/executor_audit.jsonl

USER appuser
EXPOSE 8005

HEALTHCHECK --interval=10s --timeout=3s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8005/health')"

CMD ["gunicorn", "-b", "0.0.0.0:8005", "--workers", "1", "--threads", "2", "services.executor.app:app"]
