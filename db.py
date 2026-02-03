import psycopg2
from psycopg2.extras import RealDictCursor
import json
import os

def create_er_database_safe(
    dbname,
    user,
    password,
    host="localhost",
    port=5432
):
    # Step 1: Connect to default postgres DB to check if target DB exists
    conn = psycopg2.connect(
        dbname="postgres",
        user=user,
        password=password,
        host=host,
        port=port
    )
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (dbname,))
    exists = cur.fetchone()

    if not exists:
        cur.execute(f"CREATE DATABASE {dbname};")
        print(f"Database '{dbname}' created.")
    else:
        print(f"Database '{dbname}' already exists.")

    cur.close()
    conn.close()

    # Step 2: Connect to target DB and create tables safely
    conn = psycopg2.connect(
        dbname=dbname,
        user=user,
        password=password,
        host=host,
        port=port
    )
    conn.autocommit = True
    cur = conn.cursor()

    commands = [
        # Optional but useful
        """
        CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
        """,

        # ---------- CUSTOMER (Hybrid POC Design) ----------
        """
        CREATE TABLE IF NOT EXISTS customer (
            id INTEGER PRIMARY KEY,  -- your "customer_id"
            first_name VARCHAR(100) NOT NULL,
            last_name VARCHAR(100) NOT NULL,
            preferred_name VARCHAR(100),
            phone_number VARCHAR(30),

            address JSONB,
            employment_info JSONB,

            total_assets NUMERIC(12, 2),
            financial_data JSONB,   -- accounts + transactions live here

            call_reason TEXT,
            contact_center VARCHAR(50),

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,

        # ---------- PROMOTION ----------
        """
        CREATE TABLE IF NOT EXISTS promotion (
            id SERIAL PRIMARY KEY,
            description TEXT NOT NULL,
            conditions JSONB,
            requirements JSONB
        );
        """,

        # ---------- PROMOTION OFFER (Junction Table) ----------
        """
        CREATE TABLE IF NOT EXISTS promotionoffer (
            id SERIAL PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            promotion_id INTEGER NOT NULL,
            date DATE NOT NULL,
            status VARCHAR(50),

            CONSTRAINT fk_customer
                FOREIGN KEY(customer_id)
                REFERENCES customer(id)
                ON DELETE CASCADE,

            CONSTRAINT fk_promotion
                FOREIGN KEY(promotion_id)
                REFERENCES promotion(id)
                ON DELETE CASCADE,

            CONSTRAINT unique_offer
                UNIQUE(customer_id, promotion_id, date)
        );
        """,

        # ---------- INTERACTION ----------
        """
        CREATE TABLE IF NOT EXISTS interaction (
            id SERIAL PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            type VARCHAR(50) NOT NULL,
            summary TEXT,
            date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

            CONSTRAINT fk_customer_interaction
                FOREIGN KEY(customer_id)
                REFERENCES customer(id)
                ON DELETE CASCADE
        );
        """
    ]

    for cmd in commands:
        cur.execute(cmd)

    cur.close()
    conn.close()

    print(f"Tables created/verified in database '{dbname}'.")

class DatabaseManager:
    def __init__(self, dbname, user, password, host="localhost", port=5432):
        self.params = {
            "dbname": dbname,
            "user": user,
            "password": password,
            "host": host,
            "port": port
        }

    def execute(self, query, vars=None):
        with psycopg2.connect(**self.params) as conn:
            with conn.cursor() as cur:
                cur.execute(query, vars)
                conn.commit()

    def fetch_one(self, query, vars=None):
        with psycopg2.connect(**self.params) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, vars)
                return cur.fetchone()

    def fetch_all(self, query, vars=None):
        with psycopg2.connect(**self.params) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, vars)
                return cur.fetchall()

class CustomerRepository:
    def __init__(self, db):
        self.db = db

    # ---------- Create / Upsert from Full Payload ----------
    def upsert_from_payload(self, payload: dict):
        query = """
        INSERT INTO customer (
            id,
            first_name,
            last_name,
            preferred_name,
            phone_number,
            address,
            employment_info,
            total_assets,
            financial_data,
            call_reason,
            contact_center
        )
        VALUES (%s, %s, %s, %s, %s,
                %s::jsonb, %s::jsonb, %s, %s::jsonb,
                %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name,
            preferred_name = EXCLUDED.preferred_name,
            phone_number = EXCLUDED.phone_number,
            address = EXCLUDED.address,
            employment_info = EXCLUDED.employment_info,
            total_assets = EXCLUDED.total_assets,
            financial_data = EXCLUDED.financial_data,
            call_reason = EXCLUDED.call_reason,
            contact_center = EXCLUDED.contact_center;
        """

        return self.db.execute(query, (
            int(payload["customer_id"]),
            payload["first_name"],
            payload["last_name"],
            payload.get("preferred_name"),
            payload.get("phone_number"),
            json.dumps(payload.get("address")),
            json.dumps(payload.get("employment_info")),
            payload.get("total_assets"),
            json.dumps({
                "accounts": payload.get("accounts", []),
                "last_digital_visit": payload.get("last_digital_visit")
            }),
            payload.get("call_reason"),
            payload.get("contact_center")
        ))

    # ---------- Queries ----------
    def get_by_id(self, customer_id):
        return self.db.fetch_one(
            "SELECT * FROM customer WHERE id = %s;",
            (customer_id,)
        )

    def get_all(self):
        return self.db.fetch_all(
            "SELECT * FROM customer ORDER BY created_at DESC;"
        )

    # ---------- Controlled Updates ----------
    def update_phone(self, customer_id, phone_number):
        return self.db.execute(
            "UPDATE customer SET phone_number = %s WHERE id = %s;",
            (phone_number, customer_id)
        )

    def update_call_reason(self, customer_id, call_reason):
        return self.db.execute(
            "UPDATE customer SET call_reason = %s WHERE id = %s;",
            (call_reason, customer_id)
        )

    def patch_financial_data(self, customer_id, patch: dict):
        """
        Merges new JSON into existing financial_data
        """
        query = """
        UPDATE customer
        SET financial_data = financial_data || %s::jsonb
        WHERE id = %s;
        """
        return self.db.execute(query, (json.dumps(patch), customer_id))

    def delete(self, customer_id):
        return self.db.execute(
            "DELETE FROM customer WHERE id = %s;",
            (customer_id,)
        )

class InteractionRepository:
    def __init__(self, db):
        self.db = db

    def create(self, customer_id, type_, summary):
        query = """
        INSERT INTO interaction (
            customer_id,
            type,
            summary
        )
        VALUES (%s, %s, %s)
        RETURNING id;
        """
        return self.db.fetch_one(query, (customer_id, type_, summary))["id"]

    def get_for_customer(self, customer_id):
        return self.db.fetch_all(
            """
            SELECT *
            FROM interaction
            WHERE customer_id = %s
            ORDER BY date DESC;
            """,
            (customer_id,)
        )

    def delete(self, interaction_id):
        return self.db.execute(
            "DELETE FROM interaction WHERE id = %s;",
            (interaction_id,)
        )

class PromotionRepository:
    def __init__(self, db):
        self.db = db

    def create(self, description, conditions_dict=None, requirements_dict=None):
        query = """
        INSERT INTO promotion (description, conditions, requirements)
        VALUES (%s, %s::jsonb, %s::jsonb)
        RETURNING id;
        """
        # Convert dicts to JSON strings
        return self.db.fetch_one(query, (
            description, 
            json.dumps(conditions_dict) if conditions_dict else None, 
            json.dumps(requirements_dict) if requirements_dict else None
        ))["id"]

    def get_by_id(self, promotion_id):
        return self.db.fetch_one(
            "SELECT * FROM promotion WHERE id = %s;",
            (promotion_id,)
        )

    def get_all(self):
        return self.db.fetch_all(
            "SELECT * FROM promotion ORDER BY id;"
        )

    def delete(self, promotion_id):
        return self.db.execute(
            "DELETE FROM promotion WHERE id = %s;",
            (promotion_id,)
        )

class PromotionOfferRepository:
    def __init__(self, db):
        self.db = db

    def assign(self, customer_id, promotion_id, status="ACTIVE"):
        query = """
        INSERT INTO promotionoffer (
            customer_id,
            promotion_id,
            date,
            status
        )
        VALUES (%s, %s, CURRENT_DATE, %s)
        RETURNING id;
        """
        return self.db.fetch_one(query, (customer_id, promotion_id, status))["id"]

    def get_for_customer(self, customer_id):
        return self.db.fetch_all(
            """
            SELECT po.id,
                   po.date,
                   po.status,
                   p.id AS promotion_id,
                   p.description
            FROM promotionoffer po
            JOIN promotion p ON po.promotion_id = p.id
            WHERE po.customer_id = %s
            ORDER BY po.date DESC;
            """,
            (customer_id,)
        )

    def update_status(self, offer_id, status):
        return self.db.execute(
            "UPDATE promotionoffer SET status = %s WHERE id = %s;",
            (status, offer_id)
        )

    def revoke(self, offer_id):
        return self.db.execute(
            "DELETE FROM promotionoffer WHERE id = %s;",
            (offer_id,)
        )

if __name__ == "__main__":
    # --- Configuration ---
    DB_NAME = os.getenv("DB_NAME", "td_poc")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASS = os.getenv("DB_PASS", "password")

    # 1. Initialize the Database Schema
    create_er_database_safe(DB_NAME, DB_USER, DB_PASS)

    # 2. Initialize Manager and Repositories
    db = DatabaseManager(DB_NAME, DB_USER, DB_PASS)
    cust_repo = CustomerRepository(db)
    int_repo = InteractionRepository(db)
    promo_repo = PromotionRepository(db)
    offer_repo = PromotionOfferRepository(db)

    # 3. Example Customer Payload (The "Hybrid" Data)
    sample_payload = {
        "customer_id": 1001,
        "first_name": "John",
        "last_name": "Doe",
        "preferred_name": "Johnny",
        "phone_number": "555-0123",
        "address": {
            "street": "123 Maple Ave",
            "city": "Toronto",
            "postal_code": "M5V 2T6"
        },
        "employment_info": {
            "employer": "Tech Corp",
            "position": "Developer",
            "salary": 95000
        },
        "total_assets": 250000.00,
        "accounts": [
            {"type": "Checking", "balance": 5000},
            {"type": "Savings", "balance": 45000}
        ],
        "last_digital_visit": "2023-10-27T10:00:00Z",
        "call_reason": "Inquiry about mortgage rates",
        "contact_center": "North_Regional"
    }

    # 4. Perform Operations
    print("\n--- Upserting Customer ---")
    cust_repo.upsert_from_payload(sample_payload)

    print("\n--- Creating a Promotion ---")
    promo_conditions = {
        "min_assets": 5000,
        "eligible_regions": ["North", "Central"],
        "account_type_required": "Savings"
    }
    promo_requirements = {
        "action": "deposit",
        "minimum_amount": 1000,
        "hold_period_days": 90
    }

    promo_id = promo_repo.create(
        description="High Interest Savings 5.0%",
        conditions_dict=promo_conditions,
        requirements_dict=promo_requirements
    )

    print("\n--- Assigning Promotion to Customer ---")
    offer_id = offer_repo.assign(1001, promo_id)

    print("\n--- Recording Interaction ---")
    int_repo.create(1001, "PHONE_CALL", "Customer called to ask about the 5% promo.")

    # 5. Retrieve and Verify
    customer = cust_repo.get_by_id(1001)
    interactions = int_repo.get_for_customer(1001)
    offers = offer_repo.get_for_customer(1001)

    print(f"\nCustomer: {customer['first_name']} {customer['last_name']}")
    print(f"Address from JSONB: {customer['address']['city']}")
    print(f"Latest Interaction: {interactions[0]['summary']}")
    print(f"Active Offers: {len(offers)}")