from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any
from contextlib import asynccontextmanager
import os
import time
import threading
import json
import redis

from db.db import DatabaseManager, InteractionRepository, CustomerRepository, PromotionRepository, PromotionOfferRepository, create_er_database_safe
from llama import llama_processing_layer, _load_model

# Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
DB_HOST = os.getenv("DB_HOST", "db")
DB_NAME = os.getenv("DB_NAME", "td_poc")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "password123")

SUMMARY_INTERVAL = float(os.getenv("SUMMARY_INTERVAL", "30.0"))
LOCK_TTL = 30

USE_MOCK = os.getenv("USE_MOCK_LLM", "false").lower() == "true"

# Initialize database schema
print("[App] Initializing database schema...")
create_er_database_safe(
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASS,
    host=DB_HOST,
)

# Database connection
db = DatabaseManager(
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASS,
    host=DB_HOST,
)
interaction_repo = InteractionRepository(db)
customer_repo = CustomerRepository(db)
promo_repo = PromotionRepository(db)
promo_offer_repo = PromotionOfferRepository(db)

# Redis connection
redis_client = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)

# Clean and reseed on startup
CLEAN_ON_START = os.getenv("CLEAN_ON_START", "true").lower() == "true"

def get_client_profile(customer_id: int) -> str:
    """Fetch client profile from DB and format as string for LLM (include employment/address for promotion relevance)."""
    try:
        customer = customer_repo.get_by_id(customer_id)
        if customer:
            parts = [f"Name: {customer['first_name']} {customer['last_name']}", f"Assets: {customer.get('total_assets', 'N/A')}"]
            if customer.get("address"):
                addr = customer["address"]
                if isinstance(addr, dict):
                    parts.append(f"Address: {addr.get('city', '')}, {addr.get('postal_code', '')}".strip(", "))
                else:
                    parts.append(f"Address: {addr}")
            if customer.get("employment_info"):
                emp = customer["employment_info"]
                if isinstance(emp, dict):
                    if emp.get("status") == "Student":
                        parts.append(f"Employment: Student, {emp.get('school', '')}".strip(", "))
                    elif emp.get("employer"):
                        parts.append(f"Employment: {emp.get('status', '')}, {emp.get('employer', '')}".strip(", "))
                else:
                    parts.append(f"Employment: {emp}")
            if customer.get("financial_data") and isinstance(customer["financial_data"], dict):
                accs = customer["financial_data"].get("accounts") or []
                if accs:
                    acc_str = ", ".join(f"{a.get('type', '')} {a.get('balance', 0)}" for a in accs if isinstance(a, dict))
                    parts.append(f"Accounts: {acc_str}")
            return ". ".join(p for p in parts if p)
    except Exception as e:
        print(f"[app] Error fetching customer {customer_id}: {e}")
    return "Unknown Customer"


def get_promo_catalog() -> list:
    """Fetch promotions from DB for LLM context."""
    try:
        promos = promo_repo.get_all()
        return [
            {
                "promo_id": str(p["id"]),
                "name": p.get("name", ""),
                "description": p["description"],
                "conditions": p.get("conditions"),
            }
            for p in promos
        ]
    except Exception as e:
        print(f"[app] Error fetching promos: {e}")
    return []


class SummarizerWorker(threading.Thread):
    """
    Background worker that waits for call IDs pushed into
    the 'summarize_queue' Redis list and processes them.
    """

    QUEUE_NAME = "summarize_queue"
    PENDING_SET = "pending_calls"

    def __init__(self, r_client, worker_id=1):
        super().__init__()
        self.r = r_client
        self.worker_id = worker_id
        self.running = True
        self.daemon = True

    def run(self):
        print(f"[SummarizerWorker {self.worker_id}] Started")

        while self.running:
            try:
                # Block until a call_id is available (timeout allows clean shutdown)
                result = self.r.blpop(self.QUEUE_NAME, timeout=5)

                if result:
                    _, call_id = result
                    self.r.srem(self.PENDING_SET, call_id)
                    self.process_call(call_id)

            except redis.ConnectionError as e:
                print(f"[SummarizerWorker] Redis connection error: {e}")
            except Exception as e:
                print(f"[SummarizerWorker] Unexpected error: {e}")

    def enqueue_call(self, call_id):
        """
        Push call_id to queue only if not already pending.
        """
        self.r.set(f"call:{call_id}:last_summary_ts", time.time(), nx=True)

        if self.r.sadd(self.PENDING_SET, call_id):
            self.r.rpush(self.QUEUE_NAME, call_id)

    def acquire_lock(self, call_id):
        key = f"lock:call:{call_id}"
        return self.r.set(key, self.worker_id, nx=True, ex=LOCK_TTL)

    def release_lock(self, call_id):
        self.r.delete(f"lock:call:{call_id}")

    def process_call(self, call_id):
        if not self.acquire_lock(call_id):
            return

        try:
            now = time.time()

            last_ts = float(self.r.get(f"call:{call_id}:last_summary_ts") or now)
            last_idx = int(self.r.get(f"call:{call_id}:processed_index") or 0)
            total_chunks = self.r.llen(f"call:{call_id}:chunks")

            if total_chunks == last_idx:
                return

            if now - last_ts < SUMMARY_INTERVAL:
                # Re-enqueue so it runs later
                time.sleep(1)
                self.enqueue_call(call_id)
                return

            self._do_summarize(call_id)
        finally:
            self.release_lock(call_id)

    def _do_summarize(self, call_id):
        now = time.time()

        last_idx = int(self.r.get(f"call:{call_id}:processed_index") or 0)
        total_chunks = self.r.llen(f"call:{call_id}:chunks")

        if total_chunks == last_idx:
            return None

        new_chunks = self.r.lrange(f"call:{call_id}:chunks", last_idx, -1)
        new_transcript = " ".join(new_chunks)
        actual_processed_count = last_idx + len(new_chunks)

        customer_id = self.r.get(f"call:{call_id}:customer_id") or call_id
        current_history = self.r.get(f"call:{call_id}:history") or ""

        client_profile = (
            get_client_profile(int(customer_id))
            if customer_id.isdigit()
            else "Unknown"
        )

        promo_catalog = get_promo_catalog()

        print(f"[Summary] Summarization for call {call_id} with {len(new_chunks)} new chunks...")
        start_time = time.time()
        result = llama_processing_layer(
            client_id=call_id,
            chunk_text=new_transcript,
            client_profile=client_profile,
            client_history_summary=current_history,
            promotion_catalog=promo_catalog,
            redis_store=self.r,
        )
        elapsed = time.time() - start_time
        print(f"[Summary] Call {call_id}: Summarization ({len(new_chunks)} chunks) took {elapsed:.3f} seconds")

        pipe = self.r.pipeline()
        pipe.set(f"call:{call_id}:summary", json.dumps(result["call_rolling_summary"]))
        pipe.set(f"call:{call_id}:history", json.dumps(result["client_history_summary"]))
        pipe.set(
            f"call:{call_id}:promotions",
            json.dumps(result["promotion_recommendations"]),
        )
        pipe.set(f"call:{call_id}:processed_index", actual_processed_count)
        pipe.set(f"call:{call_id}:last_summary_ts", now)
        pipe.execute()

        print(
            f"[SummarizerWorker {self.worker_id}] "
            f"Summarized {call_id} "
            f"({total_chunks - last_idx} chunks)"
        )

        return result

    def stop(self):
        self.running = False


# Global worker instance
worker = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start/stop background worker on app startup/shutdown."""
    global worker

    if not USE_MOCK:
        print("[App] Loading Llama model at startup...")
        try:
            _load_model()
            print("[App] Llama model loaded successfully.")
        except Exception as e:
            print(f"[App] Model failed to load: {e}")
            raise e  # crash startup intentionally

    if CLEAN_ON_START:
        print("[App] Cleaning Redis...")
        redis_client.flushall()

        print("[App] Cleaning and reseeding Postgres...")
        try:
            # 1. Truncate Tables
            db.execute("TRUNCATE interaction, promotionoffer, promotion, customer RESTART IDENTITY CASCADE;")

            # 2. Seed Customers
            # Customer 1 – Random caller (wrong number)
            customer_repo.upsert_from_payload({
                "customer_id": 1,
                "first_name": "Alex",
                "last_name": "Brown",
                "preferred_name": None,
                "phone_number": "4165550111",
                "address": {
                    "city": "Toronto",
                    "postal_code": "M5V2T6"
                },
                "employment_info": None,
                "total_assets": 0.00,
                "financial_data": {
                    "accounts": []
                },
                "call_reason": None,
                "contact_center": "Toronto"
            })

            # Customer 2 – Upset client (lost debit card scenario)
            customer_repo.upsert_from_payload({
                "customer_id": 2,
                "first_name": "Maria",
                "last_name": "Garcia",
                "preferred_name": "Maria",
                "phone_number": "4165550212",
                "address": {
                    "city": "Toronto",
                    "postal_code": "M5V2T6"
                },
                "employment_info": {
                    "status": "Employed",
                    "employer": "RetailCo",
                    "position": "Supervisor"
                },
                "total_assets": 18000.00,
                "financial_data": {
                    "accounts": [
                        {"type": "Checking", "balance": 2500},
                        {"type": "Savings", "balance": 15500}
                    ]
                },
                "call_reason": None,
                "contact_center": "Toronto"
            })

            # Customer 3 – University student
            customer_repo.upsert_from_payload({
                "customer_id": 3,
                "first_name": "Kevin",
                "last_name": "Li",
                "preferred_name": "Kevin",
                "phone_number": "6475551099",
                "address": {
                    "city": "Toronto",
                    "postal_code": "M4Y1A7"
                },
                "employment_info": {
                    "status": "Student",
                    "school": "University of Toronto",
                    "part_time_job": "Campus Library"
                },
                "total_assets": 3200.00,
                "financial_data": {
                    "accounts": [
                        {"type": "Student Checking", "balance": 800},
                        {"type": "Savings", "balance": 2400}
                    ]
                },
                "call_reason": None,
                "contact_center": "Toronto"
            })

            # Customer 4 – Wealth client
            customer_repo.upsert_from_payload({
                "customer_id": 4,
                "first_name": "Robert",
                "last_name": "Chen",
                "preferred_name": "Rob",
                "phone_number": "4165558891",
                "address": {
                    "city": "North York",
                    "postal_code": "M2N5S2"
                },
                "employment_info": {
                    "status": "Business Owner",
                    "industry": "Logistics"
                },
                "total_assets": 850000.00,
                "financial_data": {
                    "accounts": [
                        {"type": "Checking", "balance": 40000},
                        {"type": "Investment", "balance": 810000}
                    ]
                },
                "call_reason": None,
                "contact_center": "Toronto"
            })

            # Customer 5 – Mortgage client
            customer_repo.upsert_from_payload({
                "customer_id": 5,
                "first_name": "Emily",
                "last_name": "Watson",
                "preferred_name": "Emily",
                "phone_number": "4165553333",
                "address": {
                    "city": "Toronto",
                    "postal_code": "M6J3K1"
                },
                "employment_info": {
                    "status": "Employed",
                    "employer": "City of Toronto"
                },
                "total_assets": 220000.00,
                "financial_data": {
                    "accounts": [
                        {"type": "Checking", "balance": 6000},
                        {"type": "Mortgage", "balance": 480000}
                    ]
                },
                "call_reason": None,
                "contact_center": "Toronto"
            })

            # 3. Seed Promotions (order: id 1 = Student for scenario 3, match Colab catalog)
            promo_repo.create(
                description='Student High-Interest Savings: No monthly fee high-interest savings account for students. Good interest rate, no minimum balance. For students at recognized institutions.',
                conditions_dict={"student": True, "max_assets": 50000}
            )
            promo_repo.create(
                description='10% off credit card annual fee',
                conditions_dict={"min_assets": 100000}
            )
            promo_repo.create(
                description='Investment Platform Fee Waiver: Promotional fee waiver on TD Direct Investing.',
                conditions_dict={"min_assets": 500000}
            )
            promo_repo.create(
                description='Mortgage Renewal Cash Back: Cash back for renewing mortgage with TD.',
                conditions_dict={"has_mortgage": True}
            )
            promo_repo.create(
                description='New Savings Account Bonus: Bonus interest for new high-interest savings in 90 days.',
                conditions_dict={}
            )

            print("[App] Cleanup complete.")
        except Exception as e:
            print(f"[App] Cleanup warning: {e}")

    worker = SummarizerWorker(redis_client)
    worker.start()
    print("[App] Summarizer worker started")
    yield
    worker.stop()
    worker.join(timeout=2)
    print("[App] Summarizer worker stopped")


app = FastAPI(title="Summarizer Service", lifespan=lifespan)



# ============== Request/Response Models ==============

class GetSummaryResponse(BaseModel):
    call_id: str
    rolling_summary: Any  # Structured dict with bullets, crm_paragraph
    history_summary: str
    promotions: Any
    chunks_processed: int


class SaveSummaryRequest(BaseModel):
    call_id: str
    customer_id: int
    summary: str  # The (potentially edited) CRM paragraph


class SaveSummaryResponse(BaseModel):
    interaction_id: int
    summary: str

class CustomerHistoryResponse(BaseModel):
    customer_id: int
    profile: dict
    interactions: list
    promotions_offered: list


# ============== Endpoints ==============
@app.get("/customer_history/{customer_id}", response_model=CustomerHistoryResponse)
def get_customer_history(customer_id: int):
    """
    Fetch customer history for display at the beginning of a call.
    Includes:
    - Profile info
    - Past interactions
    - Promotions offered
    """
    try:
        # 1. Fetch Customer
        customer = customer_repo.get_by_id(customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")

        # 2. Fetch Interactions (ensure list for frontend)
        interactions = interaction_repo.get_for_customer(customer_id) or []

        # 3. Fetch Promotions Offered (ensure list for frontend)
        offers = promo_offer_repo.get_for_customer(customer_id) or []

        # 4. Format profile cleanly
        profile = {
            "name": f"{customer['first_name']} {customer['last_name']}",
            "preferred_name": customer.get("preferred_name"),
            "phone_number": customer.get("phone_number"),
            "total_assets": float(customer["total_assets"]) if customer.get("total_assets") else None,
            "address": customer.get("address"),
            "employment_info": customer.get("employment_info"),
            "financial_data": customer.get("financial_data"),
            "call_reason": customer.get("call_reason"),
            "contact_center": customer.get("contact_center"),
        }

        return {
            "customer_id": customer_id,
            "profile": profile,
            "interactions": interactions,
            "promotions_offered": offers,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/summary/{call_id}", response_model=GetSummaryResponse)
def get_summary(call_id: str):
    """
    GET summary for a call.
    1. Polls Redis to see if the background worker finishes the job.
    2. If no one is working on it and chunks remain, processes them immediately.
    """
    try:
        total_chunks = redis_client.llen(f"call:{call_id}:chunks")
        lock_key = f"lock:call:{call_id}"

        max_wait = 90
        start_wait = time.time()

        while time.time() - start_wait < max_wait:
            last_idx = int(redis_client.get(f"call:{call_id}:processed_index") or 0)

            # Case 1: All chunks are already processed
            if last_idx >= total_chunks:
                break

            # Case 2: Check if a worker is currently holding the lock
            lock_owner = redis_client.get(lock_key)
            if lock_owner and lock_owner != "api":
                # A worker is already processing, so we wait and poll
                time.sleep(2)
                continue

            # Case 3: No one is processing, API takes over
            if redis_client.set(lock_key, "api", nx=True, ex=LOCK_TTL):
                try:
                    # Re-check index inside the lock to prevent double-processing
                    current_idx = int(redis_client.get(f"call:{call_id}:processed_index") or 0)
                    if current_idx < total_chunks:
                        # --- Process Remaining Chunks ---
                        new_chunks = redis_client.lrange(f"call:{call_id}:chunks", current_idx, -1)
                        new_transcript = " ".join(new_chunks)

                        customer_id = redis_client.get(f"call:{call_id}:customer_id") or call_id
                        current_history = redis_client.get(f"call:{call_id}:history") or ""
                        client_profile = get_client_profile(int(customer_id)) if str(customer_id).isdigit() else "Unknown"
                        promo_catalog = get_promo_catalog()

                        result = llama_processing_layer(
                            client_id=call_id,
                            chunk_text=new_transcript,
                            client_profile=client_profile,
                            client_history_summary=current_history,
                            promotion_catalog=promo_catalog,
                            redis_store=redis_client
                        )

                        pipe = redis_client.pipeline()
                        pipe.set(f"call:{call_id}:summary", json.dumps(result["call_rolling_summary"]))
                        pipe.set(f"call:{call_id}:history", result["client_history_summary"].get("history_summary", ""))
                        pipe.set(f"call:{call_id}:promotions", json.dumps(result["promotion_recommendations"]))
                        pipe.set(f"call:{call_id}:processed_index", total_chunks)
                        pipe.execute()
                    break # Work is done
                finally:
                    redis_client.delete(lock_key)

            time.sleep(1)

        # --- Final Data Retrieval ---
        summary_json = redis_client.get(f"call:{call_id}:summary")
        if not summary_json:
            raise HTTPException(status_code=404, detail=f"No summary found for call {call_id}")

        rolling_summary = json.loads(summary_json) if summary_json else {}
        history_raw = redis_client.get(f"call:{call_id}:history") or ""
        try:
            history_obj = json.loads(history_raw) if history_raw else {}
        except json.JSONDecodeError:
            history_obj = {"history_summary": history_raw, "client_summary": history_raw}
        promos_json = redis_client.get(f"call:{call_id}:promotions") or "{}"
        promotions = json.loads(promos_json) if promos_json else {"recommendations": [], "no_relevant_flag": True}
        chunks_processed = int(redis_client.get(f"call:{call_id}:processed_index") or 0)

        return {
            "call_id": call_id,
            "rolling_summary": rolling_summary,
            "history_summary": history_obj.get("history_summary", ""),
            "client_summary": history_obj.get("client_summary", ""),
            "promotions": promotions,
            "chunks_processed": chunks_processed,
        }

    except HTTPException: raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/promotions/{call_id}")
def get_promotions(call_id: str):
    """
    GET current promotions for a call.
    Frontend can poll this periodically during the call.
    """
    try:
        promos_json = redis_client.get(f"call:{call_id}:promotions")
        if not promos_json:
            return {"recommendations": [], "no_relevant_flag": True}

        try:
            return json.loads(promos_json)
        except json.JSONDecodeError:
            return {"recommendations": [], "no_relevant_flag": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/save_summary", response_model=SaveSummaryResponse)
def save_summary(payload: SaveSummaryRequest):
    """
    POST to save the (potentially edited) summary to Postgres.
    Called after user reviews/edits the summary in frontend.
    """
    try:
        # Save to Postgres
        interaction_id = interaction_repo.create(
            customer_id=payload.customer_id,
            type_="PHONE_CALL",
            summary=payload.summary,
        )

        # Clean up Redis
        pipe = redis_client.pipeline()

        keys_to_del = [
            f"call:{payload.call_id}:chunks",
            f"call:{payload.call_id}:summary",
            f"call:{payload.call_id}:history",
            f"call:{payload.call_id}:promotions",
            f"call:{payload.call_id}:processed_index",
            f"call:{payload.call_id}:last_summary_ts",
            f"call:{payload.call_id}:customer_id",
            f"lock:call:{payload.call_id}"
        ]
        for k in keys_to_del: pipe.delete(k)

        # Control Keys
        pipe.srem("active_calls", payload.call_id)
        pipe.srem("pending_calls", payload.call_id)
        pipe.lrem("summarize_queue", 0, payload.call_id)

        pipe.execute()

        return {
            "interaction_id": interaction_id,
            "summary": payload.summary,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "worker_running": worker.is_alive() if worker else False}
