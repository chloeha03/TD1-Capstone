ARG BASE_IMAGE=nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04
FROM ${BASE_IMAGE}

RUN apt-get update && apt-get install -y \
    python3-pip python3-dev \
    ffmpeg libsndfile1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN pip install --upgrade pip

COPY services/transcriber/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/transcriber/app.py .

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
