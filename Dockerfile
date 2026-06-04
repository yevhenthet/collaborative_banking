FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN apt-get update -q && apt-get install -y -q fonts-liberation && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Persistent volume for SQLite will be mounted at /data
RUN mkdir -p /data

EXPOSE 8080

# Bind explicitly to 0.0.0.0:8080 — required by fly-proxy.
# run.py is used for local dev; uvicorn is called directly in production.
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
