from transformers import AutoTokenizer, AutoModelForCausalLM
import os

MODEL_ID = "meta-llama/Meta-Llama-3.1-8B-Instruct"
LOCAL_DIR = "./models/meta-llama-3.1-8b-instruct"
HF_TOKEN = os.getenv("HF_TOKEN")

# Download and SAVE properly
tokenizer = AutoTokenizer.from_pretrained(
    MODEL_ID,
    token=HF_TOKEN
)

model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    token=HF_TOKEN
)

# Save clean folder
tokenizer.save_pretrained(LOCAL_DIR)
model.save_pretrained(LOCAL_DIR)

print("Model downloaded and saved correctly.")
