FROM python:3.11-slim-bullseye 

RUN apt-get update && apt-get install -y \
    build-essential \ 
    libxml2-dev \ 
    libxslt1-dev \
    libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --timeout=1000 -r requirements.txt

COPY . .

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app

USER appuser

CMD ["python", "main.py"]


