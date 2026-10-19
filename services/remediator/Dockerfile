FROM python:3.12-slim

WORKDIR /app

RUN groupadd -r appgroup && useradd -r -g appgroup appuser

COPY services/remediator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/ /app/services/
ENV PYTHONPATH=/app
ENV REMEDIATOR_PORT=8004

USER appuser
EXPOSE 8004

HEALTHCHECK --interval=10s --timeout=3s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8004/health')"

CMD ["gunicorn", "-b", "0.0.0.0:8004", "--workers", "1", "--threads", "4", "services.remediator.app:app"]
