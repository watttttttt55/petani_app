FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gdal-bin libgdal-dev libgeos-dev libproj-dev build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables for GDAL
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

# Set workdir
WORKDIR /app

# Copy all project files (termasuk .env dan templates/static)
COPY . /app

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Expose port (opsional)
EXPOSE 10000

# Run the Flask app with Gunicorn
CMD exec gunicorn --bind "0.0.0.0:${PORT:-5000}" app:app
