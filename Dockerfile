FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/data
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 1000 --create-home monitor && mkdir /data && chown monitor:monitor /data
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app/services/ backend/app/services/
COPY backend/app/utils/ backend/app/utils/
COPY backend/app/core/ backend/app/core/
COPY backend/app/data/ backend/app/data/
COPY monitor/ monitor/
COPY LICENSE README.md ./
USER monitor
EXPOSE 8000
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["python", "-m", "uvicorn", "monitor.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--loop", "asyncio", "--workers", "1"]
