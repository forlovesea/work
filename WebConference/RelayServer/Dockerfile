FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY static ./static
COPY server.py .
RUN useradd --uid 10001 --create-home meeting && mkdir -p /app/data /app/models \
    && chown -R meeting:meeting /app/data
USER meeting
EXPOSE 8000
CMD ["python", "server.py", "--host", "127.0.0.1", "--port", "8000"]
