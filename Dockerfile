FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Persistent volume for SQLite will be mounted at /data
RUN mkdir -p /data

EXPOSE 8080

CMD ["python", "run.py"]
