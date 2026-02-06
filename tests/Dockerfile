# tests/Dockerfile
FROM python:3.11-slim

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
COPY db/db.py /app/db.py
COPY tests/db_test.py /app/db_test.py

CMD ["python", "-u", "db_test.py"]
