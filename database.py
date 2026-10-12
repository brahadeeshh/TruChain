
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "truchain.db"


def get_connection():
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS claims (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                claim_type TEXT NOT NULL,
                claimed_amount REAL NOT NULL,
                reference_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                verified_amount REAL,
                explanation TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                claim_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                details TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (claim_id) REFERENCES claims(id)
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS trusted_records (
                reference_id TEXT PRIMARY KEY,
                claim_type TEXT NOT NULL,
                verified_amount REAL NOT NULL,
                source_label TEXT NOT NULL
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS blockchain_audits (
                claim_id INTEGER PRIMARY KEY,
                blockchain_status TEXT NOT NULL,
                transaction_hash TEXT,
                commitment_hash TEXT,
                claim_id_hash TEXT,
                salt TEXT,
                message TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (claim_id) REFERENCES claims(id)
            )
        """)

        demo_records = [
            (
                "PAYROLL-TEST-101",
                "monthly_income",
                30000,
                "Demo Payroll Source A",
            ),
            (
                "PAYROLL-TEST-102",
                "monthly_income",
                22000,
                "Demo Payroll Source B",
            ),
            (
                "PAYROLL-TEST-103",
                "monthly_income",
                45000,
                "Demo Payroll Source C",
            ),
            (
                "BANK-REF-201",
                "bank_balance",
                150000,
                "Demo Banking Record (State Bank)",
            ),
            (
                "BANK-REF-202",
                "bank_balance",
                75000,
                "Demo Banking Record (HDFC Bank)",
            ),
            (
                "EXPENSE-REF-301",
                "monthly_expenses",
                18000,
                "Demo Housing & Utilities Record",
            ),
            (
                "LOAN-REF-401",
                "loans_liabilities",
                500000,
                "Demo Credit Bureau Liability Record",
            ),
            (
                "TAX-REF-501",
                "tax_financial_documents",
                450000,
                "Demo Tax Authority Filing Record",
            ),
            (
                "CLAIM-REF-601",
                "general_financial_claim",
                25000,
                "Demo Grants & Subsidy Reference",
            ),
        ]

        connection.executemany("""
            INSERT OR IGNORE INTO trusted_records
            (reference_id, claim_type, verified_amount, source_label)
            VALUES (?, ?, ?, ?)
        """, demo_records)


def get_trusted_record(reference_id):
    with get_connection() as connection:
        row = connection.execute("""
            SELECT reference_id, claim_type, verified_amount, source_label
            FROM trusted_records
            WHERE reference_id = ?
        """, (reference_id,)).fetchone()

    return dict(row) if row else None