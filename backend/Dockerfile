FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Remove build tools after compilation to shrink image (compiled .so files are kept)
RUN apt-get purge -y --auto-remove gcc g++ build-essential \
    && rm -rf /var/lib/apt/lists/* /tmp/* /root/.cache

# Copy project
COPY . .

# Create PDF output directory
RUN mkdir -p /app/contracts_pdf

# Expose port
EXPOSE 8000

# Run migrations and start server
CMD python manage.py migrate && \
    python manage.py runserver 0.0.0.0:8000