FROM python:3.11-slim

ENV PYTHONUNBUFFERED=True
ENV PYTHONDONTWRITEBYTECODE=True

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy the application code and modules
COPY main.py .
COPY config/ ./config/
COPY models/ ./models/
COPY database/ ./database/
COPY services/ ./services/
COPY api/ ./api/
COPY utils/ ./utils/

RUN useradd --create-home --shell /bin/bash backend \
    && chown -R backend:backend /app
USER backend

CMD exec python main.py