from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any
from contextlib import asynccontextmanager
import os
import time
import threading
import json
import redis

from db.db import DatabaseManager, InteractionRepository, CustomerRepository, PromotionRepository, create_er_database_safe
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

# Redis connection
redis_client = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)

# Clean and reseed on startup
CLEAN_ON_START = os.getenv("CLEAN_ON_START", "true").lower() == "true"

def get_client_profile(customer_id: int) -> str:
    """Fetch client profile from DB and format as string for LLM."""
    try:
        customer = customer_repo.get_by_id(customer_id)
        if customer:
            return f"Name: {customer['first_name']} {customer['last_name']}, Assets: {customer.get('total_assets', 'N/A')}"
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
        pipe.set(
            f"call:{call_id}:history",
            result["client_history_summary"].get("history_summary", ""),
        )
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
            customer_repo.upsert_from_payload({
                "customer_id": 1,
                "first_name": "John",
                "last_name": "Smith",
                "total_assets": 150000.00,
                "address": None, "employment_info": None, "accounts": [], 
                "call_reason": None, "contact_center": None
            })
            
            customer_repo.upsert_from_payload({
                "customer_id": 2,
                "first_name": "Jane",
                "last_name": "Doe",
                "total_assets": 250000.00,
                "address": None, "employment_info": None, "accounts": [], 
                "call_reason": None, "contact_center": None
            })

            # 3. Seed Promotions
            promo_repo.create(
                description='10% off credit card annual fee', 
                conditions_dict={"min_assets": 100000}
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


# ============== Endpoints ==============
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
        history = redis_client.get(f"call:{call_id}:history") or ""
        promos_json = redis_client.get(f"call:{call_id}:promotions") or "{}"
        promotions = json.loads(promos_json) if promos_json else {"recommendations": [], "no_relevant_flag": True}
        chunks_processed = int(redis_client.get(f"call:{call_id}:processed_index") or 0)

        return {
            "call_id": call_id,
            "rolling_summary": rolling_summary,
            "history_summary": history,
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
