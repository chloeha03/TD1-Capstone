FROM nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04

# Install Python and system deps
RUN apt-get update && apt-get install -y \
    python3-pip python3-dev \
    libpq-dev gcc git curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN pip install --upgrade pip

# GPU-enabled PyTorch
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Other Python deps
COPY services/summarizer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY db/ /app/db/
COPY services/summarizer/app.py services/summarizer/llama.py ./

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
