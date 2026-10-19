FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    DETECTOR_PORT=8003

WORKDIR /app

COPY services/detector/requirements.txt /app/services/detector/requirements.txt
RUN pip install --no-cache-dir -r /app/services/detector/requirements.txt

COPY ml /app/ml
COPY services/__init__.py /app/services/__init__.py
COPY services/detector /app/services/detector

RUN useradd --create-home --shell /bin/bash appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8003

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8003/health', timeout=2)"

CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:8003", "services.detector.app:app"]
