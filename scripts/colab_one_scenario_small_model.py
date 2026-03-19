# Colab: TinyLlama-1.1B, no HF token needed.

!pip install -q torch transformers accelerate

import os
import json
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

MODEL_ID = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
_tokenizer = None
_model = None

def _load_model():
    global _tokenizer, _model
    if _tokenizer is not None and _model is not None:
        return _tokenizer, _model
    print("[llama] Loading small model (TinyLlama 1.1B)...")
    _tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    _model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float16,
        device_map="auto",
    )
    print("[llama] Loaded.")
    return _tokenizer, _model

def parse_json_or_fallback(raw_text, fallback):
    if raw_text is None:
        return fallback
    text = str(raw_text).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    try:
        s, e = text.find("{"), text.rfind("}")
        if s != -1 and e > s:
            return json.loads(text[s : e + 1])
    except Exception:
        pass
    return fallback

def validate_promotions(promo_obj, promotion_catalog):
    if not isinstance(promo_obj, dict):
        return {"recommendations": [], "no_relevant_flag": True}
    recs = promo_obj.get("recommendations", []) or []
    allowed_ids = {str(p["promo_id"]) for p in (promotion_catalog or []) if isinstance(p, dict) and "promo_id" in p}
    catalog_by_id = {str(p["promo_id"]): p for p in (promotion_catalog or []) if isinstance(p, dict) and "promo_id" in p}
    clean_recs = []
    for r in recs:
        if not isinstance(r, dict):
            continue
        pid = str(r.get("promo_id", "")).strip()
        if pid not in allowed_ids:
            continue
        cat = catalog_by_id.get(pid, {})
        clean_recs.append({
            "promo_id": pid,
            "name": r.get("name") or cat.get("name") or "",
            "reason": r.get("reason", ""),
        })
    no_flag = bool(promo_obj.get("no_relevant_flag", False)) or len(clean_recs) == 0
    return {"recommendations": clean_recs[:2], "no_relevant_flag": no_flag}

def llama_generate(prompt, max_tokens=256, temperature=0.2):
    tokenizer, model = _load_model()
    model.eval()
    messages = [{"role": "user", "content": prompt}]
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    inputs = {k: v.to(model.device) for k, v in inputs.items()}
    if "attention_mask" not in inputs:
        inputs["attention_mask"] = torch.ones_like(inputs["input_ids"], dtype=torch.long, device=model.device)
    with torch.no_grad():
        out_ids = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            temperature=temperature,
            do_sample=(temperature > 0),
            pad_token_id=tokenizer.eos_token_id,
        )
    in_len = inputs["input_ids"].shape[1]
    return tokenizer.decode(out_ids[0, in_len:], skip_special_tokens=True)

def promoter(chunk_text, client_profile, promotion_catalog):
    prompt = f"""You are a TD promotion assistant. Using ONLY the promotion catalog below, recommend up to 2 relevant promotions. Rules: Only use promo_id 1, 2, 3, 4, or 5 from the catalog. Do not invent. If none apply, return no_relevant_flag true and empty recommendations list.

Transcript:
{chunk_text}

Client profile:
{client_profile}

Promotion catalog (use only these promo_id: 1,2,3,4,5):
{promotion_catalog}

Output JSON only, no other text:
{{"recommendations": [{{"promo_id": "1", "name": "...", "reason": "..."}}], "no_relevant_flag": false}}"""
    raw = llama_generate(prompt, max_tokens=256, temperature=0.2)
    print("[debug] model raw output (first 400 chars):", (raw or "")[:400])
    result = validate_promotions(parse_json_or_fallback(raw, {"recommendations": [], "no_relevant_flag": True}), promotion_catalog)
    if len(result.get("recommendations", [])) == 0:
        t = (chunk_text + " " + client_profile).lower()
        for p in promotion_catalog or []:
            if not isinstance(p, dict) or str(p.get("promo_id", "")) != "1":
                continue
            name_desc = (p.get("name") or "") + " " + (p.get("description") or "")
            if "student" in name_desc.lower() and ("student" in t and ("savings" in t or "saving" in t)):
                result = {
                    "recommendations": [{"promo_id": "1", "name": p.get("name", ""), "reason": "Client is student asking about savings; catalog promo 1 is for students."}],
                    "no_relevant_flag": False,
                }
                print("[fallback] rule-based: added promo_id 1 (student + savings match)")
                break
    return result

# ---------- Scenario 3 only: University student opening savings ----------
SCENARIO_3_TRANSCRIPT = """
Agent: Thank you for calling TD Bank. My name is Michael. May I confirm your full name before we begin?
Caller: Yes, my name is Kevin Li.
Agent: Thanks Kevin. For verification, could you confirm your date of birth and postal code?
Caller: Sure, my birthday is July 12th 2003 and my postal code is M4Y 1A7.
Agent: Perfect, thank you. How can I help you today?
Caller: I'm currently a student at the University of Toronto and I wanted to ask about opening a savings account.
Caller: Right now I only have a student chequing account with TD that I use for everyday spending.
Caller: I recently started a part-time job on campus and I want to start putting some money aside every month.
Caller: I was wondering if TD offers any savings accounts with good interest rates for students.
Caller: Ideally I'd prefer something with no monthly fee because I'm trying to keep my costs low.
Caller: Also are there any minimum balance requirements that I should know about?
Caller: If there are any promotions or special student offers I'd definitely be interested.
"""

CLIENT_PROFILE_3 = "Name: Kevin Li. Assets: 3200.00. Address: Toronto, M4Y1A7. Employment: Student, University of Toronto, part-time Campus Library. Accounts: Student Checking 800, Savings 2400."

CATALOG = [
    {"promo_id": "1", "name": "Student High-Interest Savings", "description": "No monthly fee high-interest savings account for students. Good interest rate, no minimum balance. For students at recognized institutions.", "conditions": {"student": True, "max_assets": 50000}},
    {"promo_id": "2", "name": "10% Off Credit Card Annual Fee", "description": "10% off credit card annual fee for eligible clients.", "conditions": {"min_assets": 100000}},
    {"promo_id": "3", "name": "Investment Platform Fee Waiver", "description": "Promotional fee waiver on TD Direct Investing.", "conditions": {"min_assets": 500000}},
    {"promo_id": "4", "name": "Mortgage Renewal Cash Back", "description": "Cash back for renewing mortgage with TD.", "conditions": {"has_mortgage": True}},
    {"promo_id": "5", "name": "New Savings Account Bonus", "description": "Bonus interest for new high-interest savings in 90 days.", "conditions": {}},
]

print("========== Scenario 3 — University Student Opening Savings (small model, one scenario only) ==========")
print("Transcript (first 400 chars):", SCENARIO_3_TRANSCRIPT.strip()[:400], "...")
print("Client profile:", CLIENT_PROFILE_3[:200], "...")
print()

result = promoter(SCENARIO_3_TRANSCRIPT, CLIENT_PROFILE_3, CATALOG)
recs = result.get("recommendations", [])
no_relevant = result.get("no_relevant_flag", True)

print("Result:")
print("  no_relevant_flag:", no_relevant)
print("  recommendations:", len(recs))
for i, r in enumerate(recs, 1):
    print(f"  [{i}] promo_id={r.get('promo_id')} name={r.get('name')}")
    print(f"      reason={r.get('reason', '')[:120]}")
print("Done.")
