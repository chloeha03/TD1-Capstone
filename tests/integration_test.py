import time
import os
import threading
import redis
import json
import sys

try:
    import db as db_module
except ImportError:
    print("Error: db.py not found. Make sure it is in the same directory.")
    sys.exit(1)

DB_HOST = os.getenv("DB_HOST", "db")
DB_NAME = os.getenv("DB_NAME", "td_poc")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "password123")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")

def wait_for_services():
    print("Waiting for Redis...")
    r = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
    for _ in range(10):
        try:
            if r.ping():
                print("Redis is ready.")
                break
        except redis.ConnectionError:
            time.sleep(2)
    else:
        print("Redis failed to connect.")
        sys.exit(1)

    print("Waiting for Postgres...")
    for _ in range(10):
        try:
            conn = db_module.psycopg2.connect(
                dbname="postgres", user=DB_USER, password=DB_PASS, host=DB_HOST
            )
            conn.close()
            print("Postgres is ready.")
            break
        except Exception as e:
            print(f"Waiting for DB... ({e})")
            time.sleep(2)

class MockSummarizerService(threading.Thread):
    def __init__(self, r_client):
        super().__init__()
        self.r = r_client
        self.running = True
        self.daemon = True

    def run(self):
        print("[Summarizer Worker] Started listening...")
        while self.running:
            active_calls = self.r.smembers("active_calls")
            for call_id in active_calls:
                self.process_call(call_id)
            time.sleep(1)

    def process_call(self, call_id):
        last_idx = int(self.r.get(f"call:{call_id}:processed_index") or 0)
        total_chunks = self.r.llen(f"call:{call_id}:chunks")

        if total_chunks > last_idx:
            new_chunks = self.r.lrange(f"call:{call_id}:chunks", last_idx, -1)
            new_text = " ".join(new_chunks)
            prev_summary = self.r.get(f"call:{call_id}:summary") or "Intro"

            updated_summary = f"{prev_summary} -> Processed({new_text[:10]}...)"

            self.r.set(f"call:{call_id}:summary", updated_summary)
            self.r.set(f"call:{call_id}:processed_index", total_chunks)
            print(f"[Summarizer Worker] Updated summary for {call_id}")

    def stop(self):
        self.running = False

def run_test_scenario():
    print("\n--- 1. Initializing Database Schema ---")
    db_module.create_er_database_safe(DB_NAME, DB_USER, DB_PASS, host=DB_HOST)

    db_manager = db_module.DatabaseManager(DB_NAME, DB_USER, DB_PASS, host=DB_HOST)

    print("Cleaning slate (Truncating tables)...")
    try:
        db_manager.execute("TRUNCATE customer, interaction, promotion, promotionoffer CASCADE;")
    except Exception as e:
        print(f"Warning during cleanup: {e}")

    cust_repo = db_module.CustomerRepository(db_manager)
    int_repo = db_module.InteractionRepository(db_manager)

    r = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
    r.flushall()

    print("\n--- 2. Creating Customer ---")
    cid = 9001
    cust_repo.upsert_from_payload({
        "customer_id": cid,
        "first_name": "Alice",
        "last_name": "Tester",
        "total_assets": 100.00,
        "address": {"city": "Wonderland"}
    })
    customer = cust_repo.get_by_id(cid)
    assert customer is not None, "Customer should exist"
    print(f"Customer created: {customer['first_name']} {customer['last_name']}")

    print("\n--- 3. Starting Call Simulation ---")
    call_id = "call_abc_123"

    worker = MockSummarizerService(r)
    worker.start()

    print("[Transcription] Chunk 1 arrived: 'Hello bank...'")
    r.rpush(f"call:{call_id}:chunks", "Hello bank")
    r.sadd("active_calls", call_id)
    time.sleep(2)

    print("[Transcription] Chunk 2 arrived: 'I need money...'")
    r.rpush(f"call:{call_id}:chunks", "I need money")
    time.sleep(2)

    current_summary = r.get(f"call:{call_id}:summary")
    print(f"[Redis Check] Current Summary: {current_summary}")
    assert "Process" in current_summary, "Summarizer didn't update Redis"

    print("\n--- 4. Finalizing Call ---")
    final_summary = r.get(f"call:{call_id}:summary")
    int_repo.create(cid, "PHONE_CALL", final_summary)

    r.srem("active_calls", call_id)
    worker.stop()
    worker.join()

    print("\n--- 5. Verifying Data Persistence ---")
    interactions = int_repo.get_for_customer(cid)

    print(f"Found {len(interactions)} interactions for customer.")
    print(f"Archived Summary: {interactions[0]['summary']}")

    assert len(interactions) == 1
    assert interactions[0]['summary'] == final_summary

    print("\nALL TESTS PASSED")

if __name__ == "__main__":
    wait_for_services()
    run_test_scenario()
