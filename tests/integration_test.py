import time
import os
import threading
import redis
import random
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

NUM_CALLS = int(os.getenv("NUM_CALLS", "10"))
NUM_WORKERS = int(os.getenv("NUM_WORKERS", "2"))
CHUNKS_PER_CALL = int(os.getenv("CHUNKS_PER_CALL", "20"))
SUMMARY_INTERVAL = float(os.getenv("SUMMARY_INTERVAL", "3.0"))
LOCK_TTL = 3

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
    def __init__(self, r_client, worker_id):
        super().__init__()
        self.r = r_client
        self.worker_id = worker_id
        self.running = True
        self.daemon = True

    def run(self):
        print(f"[Worker {self.worker_id}] Started")
        while self.running:
            active_calls = self.r.smembers("active_calls")
            for call_id in active_calls:
                self.process_call(call_id)
            time.sleep(0.2)

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

            last_ts = float(
                self.r.get(f"call:{call_id}:last_summary_ts") or 0
            )

            if now - last_ts < SUMMARY_INTERVAL:
                return

            last_idx = int(
                self.r.get(f"call:{call_id}:processed_index") or 0
            )
            total_chunks = self.r.llen(
                f"call:{call_id}:chunks"
            )

            if total_chunks == last_idx:
                return

            new_chunks = self.r.lrange(
                f"call:{call_id}:chunks", last_idx, -1
            )

            batch_text = " ".join(new_chunks)
            prev_summary = (
                self.r.get(f"call:{call_id}:summary") or "Intro"
            )

            updated_summary = (
                f"{prev_summary} "
                f"-> W{self.worker_id}"
                f"({batch_text[:20]}...)"
            )

            pipe = self.r.pipeline()
            pipe.set(f"call:{call_id}:summary", updated_summary)
            pipe.set(
                f"call:{call_id}:processed_index",
                total_chunks
            )
            pipe.set(
                f"call:{call_id}:last_summary_ts",
                now
            )
            pipe.execute()

            print(
                f"[Worker {self.worker_id}] "
                f"Summarized {call_id} "
                f"({total_chunks - last_idx} chunks)"
            )

        finally:
            self.release_lock(call_id)

    def stop(self):
        self.running = False

class TranscriptionThread(threading.Thread):
    def __init__(self, r_client, call_id, chunks):
        super().__init__()
        self.r = r_client
        self.call_id = call_id
        self.chunks = chunks

    def run(self):
        self.r.sadd("active_calls", self.call_id)

        for chunk in self.chunks:
            time.sleep(random.uniform(0.1, 0.6))
            self.r.rpush(
                f"call:{self.call_id}:chunks",
                chunk
            )
            print(
                f"[Transcription {self.call_id}] {chunk}"
            )

def run_test_scenario():
    print("\n--- Initializing Database Schema ---")
    db_module.create_er_database_safe(
        DB_NAME, DB_USER, DB_PASS, host=DB_HOST
    )

    db_manager = db_module.DatabaseManager(
        DB_NAME, DB_USER, DB_PASS, host=DB_HOST
    )

    try:
        db_manager.execute(
            "TRUNCATE customer, interaction, "
            "promotion, promotionoffer CASCADE;"
        )
    except Exception:
        pass

    cust_repo = db_module.CustomerRepository(
        db_manager
    )
    int_repo = db_module.InteractionRepository(
        db_manager
    )

    r = redis.Redis(
        host=REDIS_HOST,
        port=6379,
        decode_responses=True
    )
    r.flushall()

    cid = 9001
    cust_repo.upsert_from_payload({
        "customer_id": cid,
        "first_name": "Alice",
        "last_name": "Tester",
        "total_assets": 100.00,
        "address": {"city": "Wonderland"}
    })

    print(
        f"\nStarting test: "
        f"{NUM_CALLS} calls, "
        f"{NUM_WORKERS} workers, "
        f"{SUMMARY_INTERVAL}s summary window"
    )

    workers = []
    for i in range(NUM_WORKERS):
        w = MockSummarizerService(r, i + 1)
        w.start()
        workers.append(w)

    transcripts = {}
    threads = []

    for i in range(NUM_CALLS):
        call_id = f"call_{i}"
        chunks = [
            f"chunk_{j}_from_{call_id}"
            for j in range(CHUNKS_PER_CALL)
        ]
        transcripts[call_id] = chunks

        t = TranscriptionThread(
            r, call_id, chunks
        )
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    print(
        "\nAll transcription finished. "
        "Waiting for final summaries..."
    )

    time.sleep(SUMMARY_INTERVAL + 2)

    summaries = {}
    for call_id in transcripts:
        summary = r.get(
            f"call:{call_id}:summary"
        )
        print(
            f"[Summary] {call_id}: {summary}"
        )
        assert summary is not None
        summaries[call_id] = summary

    print("\nArchiving to Postgres...")
    for call_id, summary in summaries.items():
        int_repo.create(
            cid, "PHONE_CALL", summary
        )
        r.srem("active_calls", call_id)

    for w in workers:
        w.stop()
        w.join()

    interactions = int_repo.get_for_customer(
        cid
    )
    print(
        f"\nArchived {len(interactions)} interactions"
    )
    assert len(interactions) == NUM_CALLS

    print("\nSLOW-SUMMARIZATION STRESS TEST PASSED")

if __name__ == "__main__":
    wait_for_services()
    run_test_scenario()
