FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir requests
COPY infra/seed/seed.py /app/seed.py
CMD ["python", "seed.py"]
