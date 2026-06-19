FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt ./backend/
RUN python -m pip install --no-cache-dir --upgrade "pip>=26.1.2" \
    && pip install --no-cache-dir -r ./backend/requirements.txt

COPY backend/ ./backend/
COPY data/ /app/data/
COPY sql/ /app/sql/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import httpx; r=httpx.get('http://localhost:8000/health'); r.raise_for_status()" || exit 1

CMD ["sh", "-c", "python backend/scripts/sync_orders.py && exec uvicorn backend.main:app --host 0.0.0.0 --port 8000"]
