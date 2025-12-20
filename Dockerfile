FROM python:3.11-slim

# Install system dependencies for WeasyPrint
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libjpeg62-turbo \
    libopenjp2-7 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
# credentials.json is provided via Secret Manager or ADC in Cloud Run
# COPY credentials.json .

COPY scripts/ scripts/

# Default command
ENV PORT=8080

# Default command for Web Service (Cloud Run default)
# For Worker, override CMD with ["python", "src/main.py"]
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 src.app:app
