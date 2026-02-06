import os
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
import torch
device = "cuda" if torch.cuda.is_available() else "cpu"

# --- Configuration ---
MODEL_ID = os.getenv("MODEL_ID", "meta-llama/Meta-Llama-3.1-8B-Instruct")
LOCAL_DIR = "./models/meta-llama-3.1-8b-instruct"
HF_TOKEN = os.getenv("HF_TOKEN")
USE_MOCK = os.getenv("USE_MOCK_LLM", "false").lower() == "true"

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
    bnb_4bit_compute_dtype=torch.float16,
    device_map="auto"
)

tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, cache_dir=LOCAL_DIR, use_fast=True, token=HF_TOKEN)

model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    quantization_config=bnb_config,
    cache_dir=LOCAL_DIR,
    device_map="auto",
    token=HF_TOKEN
)

text_to_summarize = """
Climate change is one of the most pressing challenges of our time. Rising global temperatures are causing sea levels to rise, increasing the frequency of extreme weather events, and threatening biodiversity. Governments and organizations around the world are implementing policies to reduce greenhouse gas emissions, transition to renewable energy sources, and promote sustainable practices. Public awareness and individual actions, such as reducing waste and conserving energy, also play a critical role in addressing this global issue.
"""
prompt = f'Summarize the following text in 2-3 sentences:\n"{text_to_summarize}"'

inputs = tokenizer(prompt, return_tensors="pt")
inputs = {k: v.to(model.device) for k, v in inputs.items()}

# 1. Get the length of the input so we know where the generation starts
input_len = inputs["input_ids"].shape[1] 

# time it
import time
start_time = time.time()
outputs = model.generate(
    **inputs,
    max_new_tokens=128,
    temperature=0.7,
    top_p=0.9,
    do_sample=True
)
end_time = time.time()
print(f"Generation took {end_time - start_time:.2f} seconds")

# 2. Slice the output to only keep the NEW tokens
generated_tokens = outputs[0][input_len:]

# 3. Decode only the new tokens
summary = tokenizer.decode(generated_tokens, skip_special_tokens=True)
print(summary)
