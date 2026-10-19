FROM python:3.12-slim

WORKDIR /app

RUN groupadd -r appgroup && useradd -r -g appgroup appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/services/auth
ENV PYTHONPATH=/app
ENV AUTH_PORT=8002

USER appuser
EXPOSE 8002

HEALTHCHECK --interval=10s --timeout=3s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8002/health')"

CMD ["gunicorn", "-b", "0.0.0.0:8002", "--workers", "2", "--threads", "2", "services.auth.app:app"]
