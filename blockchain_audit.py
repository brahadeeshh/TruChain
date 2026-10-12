import os
import json
import secrets
from pathlib import Path

from web3 import Web3


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
BLOCKCHAIN_DIR = PROJECT_DIR / "blockchain"

RPC_URL = os.getenv(
    "TRUCHAIN_RPC_URL",
    "http://127.0.0.1:8545",
)

DEPLOYED_ADDRESS_FILE = BLOCKCHAIN_DIR / "deployed_address.json"


def get_contract_address():
    """Resolve deployed TruChainAudit contract address dynamically."""
    if os.getenv("TRUCHAIN_CONTRACT_ADDRESS"):
        return os.getenv("TRUCHAIN_CONTRACT_ADDRESS")
    if DEPLOYED_ADDRESS_FILE.exists():
        try:
            with open(DEPLOYED_ADDRESS_FILE, "r", encoding="utf-8") as file:
                data = json.load(file)
                if data.get("address"):
                    return data["address"]
        except Exception:
            pass
    return "0x5FbDB2315678afecb367f032d93F642f64180aa3"


ARTIFACT_PATH = (
    BLOCKCHAIN_DIR
    / "artifacts"
    / "contracts"
    / "TruChainAudit.sol"
    / "TruChainAudit.json"
)


# ============================================================
# WEB3 CONNECTION
# ============================================================

def get_web3():
    """Create a connection to the local Hardhat JSON-RPC node."""
    w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 5}))

    if not w3.is_connected():
        raise ConnectionError(
            f"Cannot connect to Hardhat at {RPC_URL}. "
            "Start the Hardhat node and keep it running."
        )

    return w3


def get_contract(w3):
    """Load the deployed TruChainAudit contract and its ABI."""
    if not ARTIFACT_PATH.exists():
        raise FileNotFoundError(
            f"Contract artifact not found: {ARTIFACT_PATH}. "
            "Compile the Solidity contract first."
        )

    with open(ARTIFACT_PATH, "r", encoding="utf-8") as file:
        artifact = json.load(file)

    abi = artifact.get("abi")
    if not abi:
        raise ValueError("The contract artifact does not contain an ABI.")

    contract_address = get_contract_address()
    address = Web3.to_checksum_address(contract_address)
    bytecode = w3.eth.get_code(address)

    if not bytecode or bytecode == b"":
        raise ValueError(
            f"No contract found at {address}. "
            "Deploy TruChainAudit.sol to the currently running Hardhat node "
            "and update TRUCHAIN_CONTRACT_ADDRESS if needed."
        )

    return w3.eth.contract(address=address, abi=abi)


# ============================================================
# HASH HELPERS
# ============================================================

def hash_claim_id(claim_id):
    """Create a deterministic hash of the internal claim reference."""
    claim_reference = f"TruChain:claim:{claim_id}"
    return Web3.keccak(text=claim_reference)


def create_commitment(claim_id, status, claimed_amount, verified_amount):
    """
    Create a salted commitment.

    Raw amounts and status are not written directly to the contract.
    The salt helps prevent easy guessing of the committed values.
    """
    salt = secrets.token_hex(32)

    verified_value = (
        "NONE"
        if verified_amount is None
        else str(verified_amount)
    )

    commitment_data = "|".join([
        "TruChain",
        str(claim_id),
        str(status),
        str(claimed_amount),
        verified_value,
        salt,
    ])

    commitment_hash = Web3.keccak(text=commitment_data)

    return commitment_hash, salt


# ============================================================
# BLOCKCHAIN AUDIT
# ============================================================

def commit_verification(
    claim_id,
    status,
    claimed_amount,
    verified_amount=None,
):
    """
    Record a verification commitment on the local blockchain.

    Returns a dictionary containing:
        blockchain_status
        transaction_hash
        commitment_hash
        claim_id_hash
        salt
        message

    IMPORTANT:
    The caller should store the salt securely in the database.
    Do not expose the salt through public API responses.
    """

    result = {
        "blockchain_status": "PENDING",
        "transaction_hash": None,
        "commitment_hash": None,
        "claim_id_hash": None,
        "salt": None,
        "message": "",
    }

    try:
        # Connect to the Hardhat node.
        w3 = get_web3()

        # Load the deployed contract.
        contract = get_contract(w3)

        # Use the first unlocked Hardhat account for local testing.
        accounts = w3.eth.accounts
        if not accounts:
            raise RuntimeError("No unlocked Hardhat accounts are available.")

        sender = Web3.to_checksum_address(accounts[0])

        # Generate the claim identifier hash and salted commitment.
        claim_id_hash_bytes = hash_claim_id(claim_id)

        commitment_hash_bytes, salt = create_commitment(
            claim_id=claim_id,
            status=status,
            claimed_amount=claimed_amount,
            verified_amount=verified_amount,
        )

        claim_id_hash_hex = claim_id_hash_bytes.hex()
        commitment_hash_hex = commitment_hash_bytes.hex()

        result["claim_id_hash"] = claim_id_hash_hex
        result["commitment_hash"] = commitment_hash_hex
        result["salt"] = salt

        # Submit the transaction to the smart contract.
        transaction = contract.functions.commitAudit(
            claim_id_hash_bytes,
            commitment_hash_bytes,
        ).transact({
            "from": sender,
            "gas": 300000,
        })

        # Wait for the transaction to be mined.
        receipt = w3.eth.wait_for_transaction_receipt(
            transaction,
            timeout=120,
        )

        raw_tx_hash = receipt["transactionHash"].hex()
        result["transaction_hash"] = raw_tx_hash if raw_tx_hash.startswith("0x") else f"0x{raw_tx_hash}"

        if receipt["status"] != 1:
            result["blockchain_status"] = "FAILED"
            result["message"] = "Blockchain transaction reverted."
            return result

        result["blockchain_status"] = "RECORDED"
        result["message"] = (
            "Audit commitment recorded on the local blockchain."
        )

        return result

    except Exception as error:
        # Preserve any hashes already calculated for diagnostics.
        result["blockchain_status"] = "PENDING"
        result["message"] = (
            f"Blockchain audit was not completed: "
            f"{type(error).__name__}: {error}"
        )
        return result


# ============================================================
# READ AND VERIFY AN EXISTING AUDIT
# ============================================================

def get_onchain_audit(claim_id):
    """
    Read the commitment stored on-chain for a claim.

    Returns the on-chain hash, timestamp and recording account.
    This function does not expose the salt or private claim data.
    """

    w3 = get_web3()
    contract = get_contract(w3)

    claim_id_hash_bytes = hash_claim_id(claim_id)

    commitment_hash, timestamp, recorded_by = (
        contract.functions.getAudit(
            claim_id_hash_bytes
        ).call()
    )

    return {
        "claim_id_hash": claim_id_hash_bytes.hex(),
        "commitment_hash": commitment_hash.hex(),
        "timestamp": int(timestamp),
        "recorded_by": recorded_by,
    }


def verify_onchain_commitment(claim_id, expected_commitment_hash):
    """
    Check whether the expected commitment matches the contract record.

    expected_commitment_hash must be the exact 32-byte hash originally
    saved in the database for this claim.
    """

    w3 = get_web3()
    contract = get_contract(w3)

    claim_id_hash_bytes = hash_claim_id(claim_id)

    normalized_hash = expected_commitment_hash.strip()
    if normalized_hash.startswith("0x"):
        normalized_hash = normalized_hash[2:]

    expected_hash_bytes = bytes.fromhex(normalized_hash)

    if len(expected_hash_bytes) != 32:
        raise ValueError("The commitment hash must be exactly 32 bytes.")

    return contract.functions.verifyCommitment(
        claim_id_hash_bytes,
        expected_hash_bytes,
    ).call()