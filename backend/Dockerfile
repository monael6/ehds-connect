FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY pipeline/ ./pipeline/
COPY backend/ ./backend/
COPY terminology/ ./terminology/
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
