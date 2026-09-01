FROM python:3.12-slim

WORKDIR /app/ai-ecommerce-assistant

COPY ai-ecommerce-assistant/requirements.txt .
RUN --network=host python -m pip install --no-cache-dir --upgrade "pip>=26.1.2" \
    && pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cpu \
        "torch==2.12.1+cpu" \
    && pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/backend/
COPY agent_core/ /app/agent_core/
COPY ai-ecommerce-assistant/ ./

RUN PYTHONPATH=/app python -c "import agent_core"

EXPOSE 8502

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import httpx; r=httpx.get('http://localhost:8502/ai/_stcore/health'); r.raise_for_status()" || exit 1

CMD ["streamlit", "run", "app.py", "--server.port=8502", "--server.address=0.0.0.0", "--server.headless=true", "--browser.gatherUsageStats=false", "--server.fileWatcherType=none"]
