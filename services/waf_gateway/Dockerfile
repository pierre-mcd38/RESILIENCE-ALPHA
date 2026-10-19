FROM python:3.12-slim

WORKDIR /app

RUN groupadd -r appgroup && useradd -r -g appgroup appuser

COPY services/waf_gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/waf_gateway /app/services/waf_gateway
ENV PYTHONPATH=/app
ENV WAF_PORT=8080

USER appuser
EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health')"

CMD ["gunicorn", "-b", "0.0.0.0:8080", "--workers", "2", "--threads", "4", "services.waf_gateway.app:app"]
