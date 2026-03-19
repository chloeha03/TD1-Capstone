from transformers import AutoTokenizer, AutoModelForCausalLM
import os

MODEL_ID = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
LOCAL_DIR = "./models/tinyllama-1.1b-chat-v1.0"
HF_TOKEN = os.getenv("HF_TOKEN")

# Download and SAVE properly
tokenizer = AutoTokenizer.from_pretrained(
    MODEL_ID,
    token=HF_TOKEN if HF_TOKEN else None,
)

model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    token=HF_TOKEN if HF_TOKEN else None,
)

# Save clean folder
tokenizer.save_pretrained(LOCAL_DIR)
model.save_pretrained(LOCAL_DIR)

print("Model downloaded and saved correctly.")
