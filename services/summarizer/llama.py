"""
Llama-based summarization module for the TD Summarizer Service.

Adapted from:
    https://colab.research.google.com/drive/11ovrZrcdqKJnNlgrJbCSRpH5q71ppA9H
"""

import os
import json
import threading

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

# --- Configuration ---
MODEL_ID = os.getenv("MODEL_ID", "meta-llama/Meta-Llama-3.1-8B-Instruct")
LOCAL_DIR = "/app/models/meta-llama-3.1-8b-instruct"
HF_TOKEN = os.getenv("HF_TOKEN")
USE_MOCK = os.getenv("USE_MOCK_LLM", "false").lower() == "true"

_tokenizer = None
_model = None

_load_lock = threading.Lock()

# --- Core Model Loading ---
def _load_model():
    global _tokenizer, _model

    if _tokenizer is not None and _model is not None:
        return _tokenizer, _model

    with _load_lock:
        if _model is not None:
            return _tokenizer, _model

        print("[llama] Attempting to load model locally...")

        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.float16,
        )

        try:
            # try local first
            _tokenizer = AutoTokenizer.from_pretrained(
                LOCAL_DIR,
                use_fast=True,
                local_files_only=True
            )

            _model = AutoModelForCausalLM.from_pretrained(
                LOCAL_DIR,
                quantization_config=bnb_config,
                device_map="auto",
                attn_implementation="sdpa",
                local_files_only=True
            )

            print("[llama] Loaded model from local directory.")

        except Exception as e:
            print("[llama] Local load failed. Falling back to HuggingFace Hub.")
            print(f"[llama] Reason: {e}")

            _tokenizer = AutoTokenizer.from_pretrained(
                MODEL_ID,
                use_fast=True,
                token=HF_TOKEN if HF_TOKEN else None
            )

            _model = AutoModelForCausalLM.from_pretrained(
                MODEL_ID,
                quantization_config=bnb_config,
                device_map="auto",
                attn_implementation="sdpa",
                token=HF_TOKEN if HF_TOKEN else None
            )

            print("[llama] Downloaded model from HuggingFace.")
        
        _tokenizer.pad_token = _tokenizer.eos_token
        _model.config.pad_token_id = _tokenizer.eos_token_id
        _model.generation_config.pad_token_id = _tokenizer.eos_token_id
        return _tokenizer, _model


def llama_generate(prompt, max_tokens=256, temperature=0.2):
    """Standard generation wrapper."""
    tokenizer, model = _load_model()
    model.eval()

    messages = [
        {"role": "system", "content": "You are a helpful assistant. Answer clearly and briefly."},
        {"role": "user", "content": prompt},
    ]

    try:
        tmp = tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            return_tensors="pt",
        )
        if hasattr(tmp, "shape"):
            inputs = {"input_ids": tmp.to(model.device)}
        else:
            inputs = {k: v.to(model.device) for k, v in tmp.items()}
    except Exception:
        enc = tokenizer(prompt, return_tensors="pt")
        inputs = {k: v.to(model.device) for k, v in enc.items()}

    with torch.no_grad():
        out_ids = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            temperature=temperature,
            do_sample=(temperature > 0),
            pad_token_id=tokenizer.pad_token_id,
        )

    in_len = inputs["input_ids"].shape[1]
    new_tokens = out_ids[0, in_len:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True)


# --- JSON Utilities ---

def parse_json_or_fallback(raw_text, fallback):
    if raw_text is None:
        return fallback

    text = str(raw_text).strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    try:
        s = text.find("{")
        e = text.rfind("}")
        if s != -1 and e != -1 and e > s:
            return json.loads(text[s:e+1])
    except Exception:
        pass

    return fallback


def call_summary_to_text(call_summary_obj):
    if not isinstance(call_summary_obj, dict):
        return str(call_summary_obj)

    bullets = call_summary_obj.get("bullets", [])
    para = call_summary_obj.get("crm_paragraph", "")

    lines = []
    for b in bullets[:4]:
        if isinstance(b, dict):
            ci = b.get("client_issue", "")
            aa = b.get("agent_action", "")
            ns = b.get("next_step", "")
            line = f"issue: {ci}; action: {aa}; next: {ns}"
            lines.append(line)

    out = " | ".join([x for x in lines if x.strip()])
    if para:
        out = (out + " || " + para).strip()

    return out[:1200]


def clean_summary_format(raw_summary_text):
    prompt = f"""
You are a formatting assistant for TD call summaries.

Convert the rough summary into STRICT JSON.

Return JSON only:
{{
  "bullets": [
    {{
      "client_issue": "...",
      "agent_action": "...",
      "next_step": "..."
    }}
  ],
  "crm_paragraph": "..."
}}

Rough summary:
{raw_summary_text}
"""
    cleaned = llama_generate(prompt, max_tokens=256, temperature=0.2)

    return parse_json_or_fallback(
        cleaned,
        fallback={
            "bullets": [],
            "crm_paragraph": str(raw_summary_text)
        }
    )


def call_summarizer(chunk_text, current_call_summary_text=""):
    prompt = f"""
You are a TD customer service call summarizer.

Summarize the NEW call segment in 3 to 4 bullet points.
Each bullet must include client_issue, agent_action, next_step.

After bullets, write a short CRM paragraph.

Current rolling call summary, do not repeat it:
{current_call_summary_text or "N/A"}

New transcript segment:
{chunk_text}
"""
    raw = llama_generate(prompt, max_tokens=256, temperature=0.2)
    return clean_summary_format(raw)


def client_summarizer(chunk_text, client_profile, current_history):
    prompt = f"""
You are a TD client history summarizer.

Update the ongoing client history summary using:
new call segment, client profile, existing history summary.

Rules:
Keep it concise and stable.
Track unresolved items.
Only include facts supported by inputs.
If nothing new, keep it unchanged.

Client profile:
{client_profile}

Existing client history summary:
{current_history}

New transcript segment:
{chunk_text}

Output JSON only:
{{ "history_summary": "..." }}
"""
    raw = llama_generate(prompt, max_tokens=256, temperature=0.2)

    obj = parse_json_or_fallback(
        raw,
        fallback={"history_summary": current_history}
    )

    hs = obj.get("history_summary", current_history)
    if not isinstance(hs, str) or not hs.strip():
        obj["history_summary"] = current_history

    return obj


def validate_promotions(promo_obj, promotion_catalog):
    if not isinstance(promo_obj, dict):
        return {"recommendations": [], "no_relevant_flag": True}

    recs = promo_obj.get("recommendations", [])
    if not isinstance(recs, list):
        recs = []

    allowed_ids = set()
    for p in promotion_catalog or []:
        if isinstance(p, dict) and "promo_id" in p:
            allowed_ids.add(str(p["promo_id"]))

    clean_recs = []
    for r in recs:
        if not isinstance(r, dict):
            continue
        pid = str(r.get("promo_id", "")).strip()
        if pid in allowed_ids:
            clean_recs.append(r)

    no_flag = bool(promo_obj.get("no_relevant_flag", False))
    if len(clean_recs) == 0:
        no_flag = True

    return {"recommendations": clean_recs[:2], "no_relevant_flag": no_flag}


def promoter(chunk_text, client_profile, promotion_catalog):
    prompt = f"""
You are a TD promotion assistant.

Using only the promotion catalog provided, recommend up to 2 relevant promotions.

Rules:
Select promotions only from the catalog.
Do not invent promotions.
If none apply, return no_relevant_flag true and empty list.

Transcript:
{chunk_text}

Client profile:
{client_profile}

Promotion catalog:
{promotion_catalog}

Output JSON only:
{{
  "recommendations": [
    {{
      "promo_id": "...",
      "name": "...",
      "expiry": "...",
      "description": "...",
      "fulfillment_steps": "...",
      "reason": "..."
    }}
  ],
  "no_relevant_flag": true
}}
"""
    raw = llama_generate(prompt, max_tokens=256, temperature=0.2)

    promo_obj = parse_json_or_fallback(
        raw,
        fallback={"recommendations": [], "no_relevant_flag": True}
    )

    return validate_promotions(promo_obj, promotion_catalog)


def llama_processing_layer_old(
    client_id,
    chunk_text,
    client_profile,
    client_history_summary,
    promotion_catalog,
    redis_store
):
    """Main processing layer - orchestrates all LLM calls."""
    # Get current summary from Redis
    raw_current = redis_store.get(f"call:{client_id}:summary")
    if raw_current:
        try:
            current_obj = json.loads(raw_current)
        except json.JSONDecodeError:
            current_obj = {"crm_paragraph": raw_current}
    else:
        current_obj = None
    
    current_text = call_summary_to_text(current_obj) if current_obj else ""

    call_summary_obj = call_summarizer(
        chunk_text,
        current_call_summary_text=current_text
    )

    updated_history_obj = client_summarizer(
        chunk_text,
        client_profile,
        client_history_summary
    )

    promo_obj = promoter(
        chunk_text,
        client_profile,
        promotion_catalog
    )

    return {
        "call_rolling_summary": call_summary_obj,
        "client_history_summary": updated_history_obj,
        "promotion_recommendations": promo_obj
    }

def llama_processing_layer(
    client_id,
    chunk_text,
    client_profile,
    client_history_summary,
    promotion_catalog,
    redis_store
):
    """Unified layer: One LLM call to rule them all."""
    
    # Get current summary for context
    raw_current = redis_store.get(f"call:{client_id}:summary")
    current_obj = parse_json_or_fallback(raw_current, {"bullets": [], "crm_paragraph": ""})
    current_text = call_summary_to_text(current_obj)

    # The Master Prompt
    prompt = f"""
[INST] You are a TD Bank Call Center Assistant. 
Process the new transcript segment and update the rolling call data.

CONTEXT:
- Client Profile: {client_profile}
- Existing History: {client_history_summary}
- Current Call Summary: {current_text}
- Available Promotions: {promotion_catalog}

NEW TRANSCRIPT:
{chunk_text}

OUTPUT RULES:
1. Return ONLY valid JSON.
2. 'bullets': Summarize NEW info only. Include client_issue, agent_action, next_step.
3. 'history_summary': Update ongoing client history with facts from this chunk.
4. 'promotions': Recommend up to 2 promo_ids from the catalog only if relevant.

PROMOTION RELEVANCE:
A promotion is relevant only when it:
- Addresses a current client issue or next actionable step, AND
- The client is eligible for the promotion, AND
- Offering the promotion is appropriate given the client’s current context (e.g. do not offer a credit card promotion to a client with recent credit issues, disputed charges, or billing complaints).

JSON SCHEMA:
{{
  "call_rolling_summary": {{
    "bullets": [{{ "client_issue": "...", "agent_action": "...", "next_step": "..." }}],
    "crm_paragraph": "..."
  }},
  "client_history_summary": {{ "history_summary": "..." }},
  "promotion_recommendations": {{
    "recommendations": [{{ "promo_id": "...", "name": "...", "reason": "..." }}],
    "no_relevant_flag": bool
  }}
}}
[/INST]
"""
    # Standardize on a single generation
    raw_output = llama_generate(prompt, max_tokens=700, temperature=0.1)
    
    # Parse and Validate
    result = parse_json_or_fallback(raw_output, fallback={})
    
    # Safety fallback for missing keys
    return {
        "call_rolling_summary": result.get("call_rolling_summary", {"bullets": [], "crm_paragraph": "Parsing error"}),
        "client_history_summary": result.get("client_history_summary", {"history_summary": client_history_summary}),
        "promotion_recommendations": validate_promotions(
            result.get("promotion_recommendations", {}), 
            promotion_catalog
        )
    }


def build_json_prompt(text):
    return f"""
Return ONLY valid JSON, no extra text.

Schema:
{{
  "summary": "string",
  "key_points": ["string", "string", "string"]
}}

Text:
{text}
"""

def process_new_chunk(
    client_id,
    chunk_text,
    client_profile,
    client_history_summary,
    promotion_catalog,
    redis_store
):
    result = llama_processing_layer(
        client_id=client_id,
        chunk_text=chunk_text,
        client_profile=client_profile,
        client_history_summary=client_history_summary,
        promotion_catalog=promotion_catalog,
        redis_store=redis_store
    )

    redis_store[client_id] = result["call_rolling_summary"]

    return result

def chunk_text_by_tokens(text, chunk_size=700, overlap=80):
    tokenizer, _ = _load_model()
    ids = tokenizer.encode(text)
    chunks = []
    start = 0
    while start < len(ids):
        end = min(start + chunk_size, len(ids))
        chunk_ids = ids[start:end]
        chunks.append(tokenizer.decode(chunk_ids, skip_special_tokens=True))
        if end == len(ids):
            break
        start = end - overlap
        if start < 0:
            start = 0
    return chunks

def summarize_chunk_to_json(chunk_text, max_tokens):
    prompt = build_json_prompt(chunk_text)
    raw = llama_generate(prompt, max_tokens=max_tokens, temperature=0.2)

    return parse_json_or_fallback(
        raw,
        fallback={
            "summary": "",
            "key_points": []
        }
    )

def merge_chunk_summaries(results):
    summaries = []
    points = []

    for r in results:
        if isinstance(r, dict):
            if r.get("summary"):
                summaries.append(r["summary"])
            if r.get("key_points"):
                points.extend(r["key_points"])

    seen = set()
    dedup_points = []
    for p in points:
        p2 = p.strip()
        if p2 and p2 not in seen:
            seen.add(p2)
            dedup_points.append(p2)

    final = {
        "summary": " ".join(summaries).strip(),
        "key_points": dedup_points[:10],
    }
    return final

def summarize_long_text(text, chunk_size=1200, overlap=50):
    chunks = chunk_text_by_tokens(text, chunk_size=chunk_size, overlap=overlap)
    results = []
    for i, ch in enumerate(chunks):
        r = summarize_chunk_to_json(ch, max_tokens=256)
        results.append(r)
    return merge_chunk_summaries(results)

# --- Mock Functions for Testing ---

def _mock_call_summarizer(chunk_text, current_call_summary_text=""):
    return {
        "bullets": [{"client_issue": "mock", "agent_action": "mock", "next_step": "mock"}],
        "crm_paragraph": f"Mock: {chunk_text[:50]}..."
    }

def _mock_client_summarizer(chunk_text, client_profile, current_history):
    return {"history_summary": current_history or "Mock history"}

def _mock_promoter(chunk_text, client_profile, promotion_catalog):
    return {"recommendations": [], "no_relevant_flag": True}

def _mock_llama_processing_layer(client_id, chunk_text, client_profile, client_history_summary, promotion_catalog, redis_store):
    return {
        "call_rolling_summary": _mock_call_summarizer(chunk_text),
        "client_history_summary": _mock_client_summarizer(chunk_text, client_profile, client_history_summary),
        "promotion_recommendations": _mock_promoter(chunk_text, client_profile, promotion_catalog)
    }


# --- Apply Mocks if Enabled ---
if USE_MOCK:
    print("[llama] Running in MOCK mode - no actual LLM calls")
    call_summarizer = _mock_call_summarizer
    client_summarizer = _mock_client_summarizer
    promoter = _mock_promoter
    llama_processing_layer = _mock_llama_processing_layer
