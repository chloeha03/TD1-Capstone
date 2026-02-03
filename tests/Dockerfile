# tests/Dockerfile
FROM python:3.9-slim

# Install system dependencies for psycopg2 (postgres driver)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install python libs
RUN pip install psycopg2 redis

# Copy the actual application code (db.py) and the test
# We assume the build context will be the project root
COPY db.py /app/db.py
COPY tests/integration_test.py /app/integration_test.py

CMD ["python", "-u", "integration_test.py"]
