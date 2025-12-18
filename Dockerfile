# Use Python 3.12 slim image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    build-essential \
    libpq-dev \
    gettext \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements directory (for better caching)
COPY requirements/ requirements/

# Install Python dependencies
# Use development.txt for local Docker development
# This includes base requirements + development tools (Silk, Debug Toolbar, etc.)
RUN pip install --upgrade pip && \
    pip install -r requirements/development.txt

# Copy project files
COPY . .

# Create necessary directories
RUN mkdir -p media staticfiles logs

# Expose port for Django
EXPOSE 8000

# Default command (can be overridden in docker-compose)
CMD ["python", "myapp/manage.py", "runserver", "0.0.0.0:8000"]
