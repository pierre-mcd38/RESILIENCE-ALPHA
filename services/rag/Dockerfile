FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    RAG_PORT=8006 \
    OLLAMA_BASE_URL=http://host.docker.internal:11434 \
    OLLAMA_MODEL=gemma4:e4b

WORKDIR /app

COPY services/rag/requirements.txt /app/services/rag/requirements.txt
RUN pip install --no-cache-dir -r /app/services/rag/requirements.txt

COPY AGENTS.md /app/AGENTS.md
COPY docs /app/docs
COPY services/__init__.py /app/services/__init__.py
COPY services/rag /app/services/rag

RUN useradd --create-home --shell /bin/bash appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8006

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8006/health', timeout=2)"

CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:8006", "services.rag.app:app"]
