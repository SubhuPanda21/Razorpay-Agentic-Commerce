"""AP2-inspired mandate: a cryptographically signed, bounded spending
authorization the buyer agent presents at checkout - the same shape as
Google's Agent Payments Protocol (a "Cart Mandate"): who, for how much,
at which merchant, until when. Signed with real ES256 (ECDSA / P-256),
not a symmetric HMAC trick - a tampered or expired mandate fails
signature or constraint verification, not a string comparison.

This is additive: existing /checkout/prepare callers are unaffected.
Only /uap/checkout/prepare (the protocol-aware path) requires one.
"""
import base64
import json
import time

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.exceptions import InvalidSignature

# Demo-scope keypair: generated once per process. A real deployment would
# persist this (or use Razorpay/NPCI-issued keys) rather than regenerate
# on restart - noted here rather than hidden.
_private_key = ec.generate_private_key(ec.SECP256R1())
_public_key = _private_key.public_key()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def issue_mandate(buyer_agent_id: str, merchant_id: int, max_amount: float, ttl_seconds: int = 300) -> str:
    header = {"alg": "ES256", "typ": "AP2-MANDATE"}
    payload = {
        "buyer_agent_id": buyer_agent_id,
        "merchant_id": merchant_id,
        "max_amount": max_amount,
        "exp": int(time.time()) + ttl_seconds,
    }
    signing_input = f"{_b64(json.dumps(header).encode())}.{_b64(json.dumps(payload).encode())}"
    signature = _private_key.sign(signing_input.encode(), ec.ECDSA(hashes.SHA256()))
    return f"{signing_input}.{_b64(signature)}"


def verify_mandate(token: str, merchant_id: int, amount: float, buyer_agent_id: str) -> tuple[bool, str | None]:
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
        signing_input = f"{header_b64}.{payload_b64}"
        signature = _unb64(sig_b64)
        _public_key.verify(signature, signing_input.encode(), ec.ECDSA(hashes.SHA256()))
    except (InvalidSignature, ValueError):
        return False, "invalid_mandate_signature"

    payload = json.loads(_unb64(payload_b64))
    if int(time.time()) > payload["exp"]:
        return False, "mandate_expired"
    if payload["merchant_id"] != merchant_id:
        return False, "mandate_merchant_mismatch"
    if payload["buyer_agent_id"] != buyer_agent_id:
        return False, "mandate_agent_mismatch"
    if amount > payload["max_amount"]:
        return False, f"order amount {amount} exceeds mandate ceiling {payload['max_amount']}"
    return True, None


def public_key_pem() -> str:
    """So a relying party could independently verify - the actual AP2 model."""
    return _public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
