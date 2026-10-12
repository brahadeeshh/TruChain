from contextlib import asynccontextmanager
from typing import Any, Dict, List, Literal, Optional
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from backend.database import (
    get_connection,
    get_trusted_record,
    initialize_database,
)
from backend.blockchain_audit import (
    commit_verification,
    get_onchain_audit,
    verify_onchain_commitment,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="TruChain API",
    description="Privacy-first financial claim verification with blockchain audit",
    version="2.1.0",
    lifespan=lifespan,
)


class ClaimRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)
    claim_type: Literal["monthly_income"]
    claimed_amount: float = Field(gt=0, le=100000000)
    reference_id: str = Field(min_length=1, max_length=100)


class VerifyFinancesRequest(BaseModel):
    user_id: Optional[str] = None
    claimant_name: Optional[str] = None
    claim_id: Optional[str] = None
    category: str = "monthly_income"
    claimed_amount: Optional[float] = None
    reference_id: str = Field(min_length=1, max_length=100)
    details: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    evidence_filename: Optional[str] = None
    evidence_sha256: Optional[str] = None
    submitted_at: Optional[str] = None


class VerifyRecordRequest(BaseModel):
    record_id: str


def record_audit(connection, claim_id, event_type, details):
    connection.execute(
        """
        INSERT INTO audit_events
            (claim_id, event_type, details)
        VALUES (?, ?, ?)
        """,
        (claim_id, event_type, details),
    )


def save_blockchain_audit(claim_id, result):
    """Persist the blockchain result even when its status is PENDING."""
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO blockchain_audits (
                claim_id,
                blockchain_status,
                transaction_hash,
                commitment_hash,
                claim_id_hash,
                salt,
                message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(claim_id) DO UPDATE SET
                blockchain_status = excluded.blockchain_status,
                transaction_hash = excluded.transaction_hash,
                commitment_hash = excluded.commitment_hash,
                claim_id_hash = excluded.claim_id_hash,
                salt = excluded.salt,
                message = excluded.message,
                created_at = CURRENT_TIMESTAMP
            """,
            (
                claim_id,
                result.get("blockchain_status", "PENDING"),
                result.get("transaction_hash"),
                result.get("commitment_hash"),
                result.get("claim_id_hash"),
                result.get("salt"),
                result.get("message", "Blockchain audit pending."),
            ),
        )

        record_audit(
            connection,
            claim_id,
            "BLOCKCHAIN_AUDIT",
            (
                f"Blockchain status: "
                f"{result.get('blockchain_status', 'PENDING')}. "
                f"{result.get('message', '')}"
            ),
        )


def normalize_category(cat: str) -> str:
    cleaned = cat.strip().lower()
    cleaned = cleaned.replace(" & ", "_").replace("&", "_").replace(" ", "_")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned


def extract_claimed_amount(req: VerifyFinancesRequest) -> float:
    if req.claimed_amount is not None and req.claimed_amount > 0:
        return float(req.claimed_amount)
    if req.details and isinstance(req.details, dict):
        for key, val in req.details.items():
            if any(term in key.lower() for term in ["salary", "balance", "amount", "rent", "income", "expense"]):
                try:
                    num = float(val)
                    if num > 0:
                        return num
                except (ValueError, TypeError):
                    continue
        for val in req.details.values():
            try:
                num = float(val)
                if num > 0:
                    return num
            except (ValueError, TypeError):
                continue
    return 30000.0


@app.get("/")
def root():
    return {
        "project": "TruChain",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "TruChain API",
    }


@app.get("/stats")
def get_stats():
    """Return live verification and audit statistics for the Streamlit dashboard."""
    with get_connection() as connection:
        total = connection.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
        verified = connection.execute("SELECT COUNT(*) FROM claims WHERE status = 'VERIFIED'").fetchone()[0]
        mismatch = connection.execute("SELECT COUNT(*) FROM claims WHERE status = 'MISMATCH'").fetchone()[0]
        unverified = connection.execute("SELECT COUNT(*) FROM claims WHERE status = 'UNVERIFIED'").fetchone()[0]
        blockchain_recorded = connection.execute(
            "SELECT COUNT(*) FROM blockchain_audits WHERE blockchain_status = 'RECORDED'"
        ).fetchone()[0]

    return {
        "total_claims": total,
        "verified": verified,
        "mismatch": mismatch,
        "unverified": unverified,
        "blockchain_recorded": blockchain_recorded,
    }


@app.get("/claims")
def list_claims(limit: int = 50):
    """Return a list of recent claims with blockchain audit details."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT 
                c.id as claim_id,
                c.user_id,
                c.claim_type,
                c.claimed_amount,
                c.reference_id,
                c.status,
                c.verified_amount,
                c.explanation,
                c.created_at,
                b.blockchain_status,
                b.transaction_hash,
                b.commitment_hash,
                b.message as blockchain_message
            FROM claims c
            LEFT JOIN blockchain_audits b ON c.id = b.claim_id
            ORDER BY c.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]


@app.post("/verify-finances")
def verify_finances(request: VerifyFinancesRequest):
    """
    Primary financial verification endpoint:
    1. Validates submitted claim & amounts.
    2. Compares against reference record (synthetic source).
    3. Categorizes as VERIFIED, MISMATCH, or UNVERIFIED.
    4. Computes cryptographic commitment.
    5. Commits tamper-evident audit to smart contract on Hardhat.
    6. Returns full verification & blockchain audit record.
    """
    user_id = (request.user_id or request.claimant_name or request.claim_id or "DEMO-USER-02").strip()
    category = normalize_category(request.category)
    claimed_amount = extract_claimed_amount(request)
    reference_id = request.reference_id.strip()

    # Step 1: Query synthetic reference records
    trusted = get_trusted_record(reference_id)

    if trusted is None:
        status = "UNVERIFIED"
        verified_amount = None
        source_label = "None"
        explanation = (
            f"No matching synthetic reference record found for '{reference_id}'. "
            "Manual review or valid reference identifier required."
        )
    elif trusted["claim_type"] != category:
        status = "UNVERIFIED"
        verified_amount = None
        source_label = trusted.get("source_label", "Reference Source")
        explanation = (
            f"Reference '{reference_id}' is for category '{trusted['claim_type']}', "
            f"which does not match submitted category '{category}'."
        )
    else:
        verified_amount = float(trusted["verified_amount"])
        source_label = trusted.get("source_label", "Synthetic Reference")
        diff = abs(float(claimed_amount) - verified_amount)
        if diff < 0.01:
            status = "VERIFIED"
            explanation = (
                f"The claimed amount (₹{claimed_amount:,.2f}) matches the synthetic "
                f"reference record from {source_label}."
            )
        else:
            status = "MISMATCH"
            explanation = (
                f"The claimed amount (₹{claimed_amount:,.2f}) differs from the synthetic "
                f"source record (₹{verified_amount:,.2f} from {source_label}). "
                "A mismatch is a signal for further review, not automatic proof of fraud."
            )

    # Step 2: Store claim in database
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO claims (
                user_id, claim_type, claimed_amount, reference_id,
                status, verified_amount, explanation
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, category, claimed_amount, reference_id, status, verified_amount, explanation),
        )
        claim_id = cursor.lastrowid

        record_audit(
            connection,
            claim_id,
            "CLAIM_SUBMITTED",
            f"Submitted for verification with reference {reference_id}."
            + (f" Evidence hash: {request.evidence_sha256}" if request.evidence_sha256 else ""),
        )
        record_audit(
            connection,
            claim_id,
            "VERIFICATION_COMPLETED",
            f"Status: {status}. {explanation}",
        )

    # Step 3: Record audit on Hardhat blockchain
    try:
        blockchain_result = commit_verification(
            claim_id=claim_id,
            status=status,
            claimed_amount=claimed_amount,
            verified_amount=verified_amount,
        )
        save_blockchain_audit(claim_id, blockchain_result)
    except Exception as exc:
        blockchain_result = {
            "blockchain_status": "PENDING",
            "transaction_hash": None,
            "commitment_hash": None,
            "claim_id_hash": None,
            "salt": None,
            "message": f"Blockchain audit could not be completed: {type(exc).__name__}: {exc}",
        }
        try:
            save_blockchain_audit(claim_id, blockchain_result)
        except Exception:
            pass

    return {
        "claim_id": claim_id,
        "user_id": user_id,
        "category": category,
        "claimed_amount": claimed_amount,
        "reference_id": reference_id,
        "status": status,
        "verification_status": status,
        "verified_amount": verified_amount,
        "reference_source": source_label,
        "explanation": explanation,
        "blockchain_status": blockchain_result.get("blockchain_status", "PENDING"),
        "transaction_hash": blockchain_result.get("transaction_hash"),
        "commitment_hash": blockchain_result.get("commitment_hash"),
        "claim_id_hash": blockchain_result.get("claim_id_hash"),
        "message": blockchain_result.get("message"),
        "blockchain": blockchain_result,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/verify-record")
def verify_record(request: VerifyRecordRequest):
    """Retrieve audit and blockchain record by claim_id or transaction_hash."""
    query_val = request.record_id.strip()
    with get_connection() as connection:
        row = None
        if query_val.isdigit():
            row = connection.execute(
                """
                SELECT c.*, b.blockchain_status, b.transaction_hash, b.commitment_hash,
                       b.claim_id_hash, b.message as blockchain_message
                FROM claims c
                LEFT JOIN blockchain_audits b ON c.id = b.claim_id
                WHERE c.id = ?
                """,
                (int(query_val),),
            ).fetchone()

        if not row:
            row = connection.execute(
                """
                SELECT c.*, b.blockchain_status, b.transaction_hash, b.commitment_hash,
                       b.claim_id_hash, b.message as blockchain_message
                FROM claims c
                JOIN blockchain_audits b ON c.id = b.claim_id
                WHERE b.transaction_hash = ?
                """,
                (query_val,),
            ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="No verification record found.")

    data = dict(row)
    return {
        "claim_id": data["id"],
        "user_id": data["user_id"],
        "category": data["claim_type"],
        "claimed_amount": data["claimed_amount"],
        "verified_amount": data["verified_amount"],
        "status": data["status"],
        "explanation": data["explanation"],
        "blockchain_status": data.get("blockchain_status", "PENDING"),
        "transaction_hash": data.get("transaction_hash"),
        "commitment_hash": data.get("commitment_hash"),
        "claim_id_hash": data.get("claim_id_hash"),
        "message": data.get("blockchain_message"),
        "created_at": data["created_at"],
    }


@app.get("/verify-onchain/{claim_id}")
def verify_onchain(claim_id: int):
    """Read the smart contract on-chain and verify the commitment directly."""
    with get_connection() as connection:
        audit_row = connection.execute(
            "SELECT * FROM blockchain_audits WHERE claim_id = ?",
            (claim_id,),
        ).fetchone()

    if not audit_row:
        raise HTTPException(status_code=404, detail="No blockchain audit found for this claim.")

    audit = dict(audit_row)
    if not audit.get("commitment_hash"):
        raise HTTPException(status_code=400, detail="Audit does not contain a commitment hash.")

    try:
        onchain_data = get_onchain_audit(claim_id)
        is_valid = verify_onchain_commitment(claim_id, audit["commitment_hash"])
        return {
            "claim_id": claim_id,
            "onchain_verified": is_valid,
            "onchain_commitment_hash": onchain_data["commitment_hash"],
            "expected_commitment_hash": audit["commitment_hash"],
            "recorded_by": onchain_data["recorded_by"],
            "timestamp": onchain_data["timestamp"],
            "message": "Commitment matches on-chain record perfectly." if is_valid else "Commitment mismatch on-chain!",
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to query smart contract: {type(exc).__name__}: {exc}",
        )


@app.post("/claims")
def create_claim(request: ClaimRequest):
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO claims (
                user_id,
                claim_type,
                claimed_amount,
                reference_id
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                request.user_id,
                request.claim_type,
                request.claimed_amount,
                request.reference_id,
            ),
        )

        claim_id = cursor.lastrowid

        record_audit(
            connection,
            claim_id,
            "CLAIM_CREATED",
            "Financial claim submitted for verification.",
        )

    return {
        "claim_id": claim_id,
        "status": "PENDING",
        "message": "Claim saved. Ready for verification.",
    }


@app.post("/claims/{claim_id}/verify")
def verify_claim(claim_id: int):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM claims WHERE id = ?",
            (claim_id,),
        ).fetchone()

        if row is None:
            raise HTTPException(
                status_code=404,
                detail="Claim not found",
            )

        claim = dict(row)

        if claim["status"] != "PENDING":
            blockchain_row = connection.execute(
                """
                SELECT blockchain_status, transaction_hash,
                       commitment_hash, claim_id_hash, message, created_at
                FROM blockchain_audits
                WHERE claim_id = ?
                """,
                (claim_id,),
            ).fetchone()

            return {
                "claim_id": claim_id,
                "status": claim["status"],
                "claimed_amount": claim["claimed_amount"],
                "verified_amount": claim["verified_amount"],
                "explanation": claim["explanation"],
                "blockchain": (
                    dict(blockchain_row)
                    if blockchain_row
                    else None
                ),
                "message": "This claim has already been processed.",
            }

        trusted = get_trusted_record(claim["reference_id"])

        if trusted is None:
            status = "UNVERIFIED"
            verified_amount = None
            explanation = (
                "No matching synthetic demo source record was found. "
                "Request manual review or provide a valid reference."
            )
        elif trusted["claim_type"] != claim["claim_type"]:
            status = "UNVERIFIED"
            verified_amount = None
            explanation = (
                "The source record does not support this claim type."
            )
        else:
            verified_amount = float(trusted["verified_amount"])
            if abs(float(claim["claimed_amount"]) - verified_amount) < 0.01:
                status = "VERIFIED"
                explanation = "The claimed amount matches the synthetic trusted demo record."
            else:
                status = "MISMATCH"
                explanation = (
                    "The claimed amount differs from the synthetic source record. "
                    "Request clarification or review. A mismatch alone does not establish fraud."
                )

        connection.execute(
            """
            UPDATE claims
            SET status = ?, verified_amount = ?, explanation = ?
            WHERE id = ?
            """,
            (status, verified_amount, explanation, claim_id),
        )

        record_audit(
            connection,
            claim_id,
            "VERIFICATION_COMPLETED",
            f"Status: {status}. {explanation}",
        )

    try:
        blockchain_result = commit_verification(
            claim_id=claim_id,
            status=status,
            claimed_amount=claim["claimed_amount"],
            verified_amount=verified_amount,
        )
        save_blockchain_audit(claim_id, blockchain_result)
    except Exception as exc:
        blockchain_result = {
            "blockchain_status": "PENDING",
            "transaction_hash": None,
            "commitment_hash": None,
            "claim_id_hash": None,
            "message": f"Blockchain audit could not be completed: {type(exc).__name__}",
        }
        try:
            save_blockchain_audit(claim_id, blockchain_result)
        except Exception:
            pass

    return {
        "claim_id": claim_id,
        "status": status,
        "claimed_amount": claim["claimed_amount"],
        "verified_amount": verified_amount,
        "explanation": explanation,
        "blockchain": {
            "blockchain_status": blockchain_result.get("blockchain_status", "PENDING"),
            "transaction_hash": blockchain_result.get("transaction_hash"),
            "commitment_hash": blockchain_result.get("commitment_hash"),
            "message": blockchain_result.get("message"),
        },
    }


@app.get("/claims/{claim_id}")
def get_claim(claim_id: int):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM claims WHERE id = ?",
            (claim_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Claim not found",
        )

    return dict(row)


@app.get("/audit/{claim_id}")
def get_audit(claim_id: int):
    with get_connection() as connection:
        claim = connection.execute(
            "SELECT id FROM claims WHERE id = ?",
            (claim_id,),
        ).fetchone()

        if claim is None:
            raise HTTPException(
                status_code=404,
                detail="Claim not found",
            )

        events = connection.execute(
            """
            SELECT id, claim_id, event_type, details, created_at
            FROM audit_events
            WHERE claim_id = ?
            ORDER BY id ASC
            """,
            (claim_id,),
        ).fetchall()

        blockchain_row = connection.execute(
            """
            SELECT blockchain_status, transaction_hash,
                   commitment_hash, claim_id_hash, message, created_at
            FROM blockchain_audits
            WHERE claim_id = ?
            """,
            (claim_id,),
        ).fetchone()

    return {
        "claim_id": claim_id,
        "events": [dict(event) for event in events],
        "blockchain": (
            dict(blockchain_row)
            if blockchain_row
            else None
        ),
    }