"""
Download Llama model directly to disk (no full model load in RAM).
Uses huggingface_hub.snapshot_download - same disk need (~16GB) but less RAM.
Run from project root: python3 services/summarizer/download_model_direct.py
"""
import os
from pathlib import Path

# Ensure we run from project root so LOCAL_DIR is under project
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
os.chdir(PROJECT_ROOT)

from huggingface_hub import snapshot_download

MODEL_ID = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
LOCAL_DIR = PROJECT_ROOT / "models" / "tinyllama-1.1b-chat-v1.0"
HF_TOKEN = os.getenv("HF_TOKEN")

LOCAL_DIR.mkdir(parents=True, exist_ok=True)

print("Downloading model files directly to disk (no full load in RAM)...")
snapshot_download(
    repo_id=MODEL_ID,
    local_dir=str(LOCAL_DIR),
    token=HF_TOKEN if HF_TOKEN else None,
    local_dir_use_symlinks=False,
)
print("Model downloaded and saved correctly.")
