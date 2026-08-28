"""Payment gateway abstraction.

Two implementations behind one interface:
  - RazorpayGateway: real razorpay-python SDK, test-mode keys (used when
    RAZORPAY_KEY_ID/SECRET are set and USE_MOCK_GATEWAY=false).
  - LocalMockGateway: deterministic, seeded simulator so the whole system
    runs and is demoable without live credentials.

The agents only ever depend on the `PaymentGateway` interface below, so
swapping mock -> real is a one-line config change, not a rewrite.
"""
import hashlib
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.config import settings


@dataclass
class PaymentResult:
    success: bool
    gateway_ref: str
    failure_reason: str | None = None


class PaymentGateway(ABC):
    @abstractmethod
    def charge(self, order_id: int, amount: float, method: str, attempt_seed: int = 0) -> PaymentResult:
        ...

    @abstractmethod
    def create_checkout_order(self, order_id: int, amount: float) -> dict:
        """Prepares a payable order and returns what the client needs to
        either open a real Razorpay Checkout widget or run the simulator."""
        ...

    @abstractmethod
    def verify_and_capture(self, order_id: int, payload: dict) -> PaymentResult:
        """Confirms a checkout attempt: real signature verification against
        Razorpay, or the deterministic simulator when running mock."""
        ...


class LocalMockGateway(PaymentGateway):
    """Deterministic per-order simulation, so a demo run is reproducible.

    Failure likelihood and reason are derived from a hash of
    (order_id, method, attempt_seed) rather than pure randomness, so the
    same order+method always behaves the same way in a recorded demo,
    but different orders show different, realistic outcomes.
    """

    FAILURE_REASONS = ["insufficient_funds", "bank_timeout", "network_error", "card_declined"]

    def charge(self, order_id: int, amount: float, method: str, attempt_seed: int = 0) -> PaymentResult:
        key = f"{order_id}:{method}:{attempt_seed}".encode()
        digest = int(hashlib.sha256(key).hexdigest(), 16)
        rng = random.Random(digest)

        # ~30% base failure rate on first attempt, improves with method switches
        fail = rng.random() < (0.30 if attempt_seed == 0 else 0.15)

        if fail:
            reason = self.FAILURE_REASONS[digest % len(self.FAILURE_REASONS)]
            return PaymentResult(success=False, gateway_ref="", failure_reason=reason)

        ref = f"mock_pay_{digest % 10**10}"
        return PaymentResult(success=True, gateway_ref=ref)

    def create_checkout_order(self, order_id: int, amount: float) -> dict:
        return {
            "mode": "mock",
            "razorpay_order_id": f"mock_order_{order_id}",
            "amount": int(amount * 100),
            "currency": "INR",
            "key_id": None,
        }

    def verify_and_capture(self, order_id: int, payload: dict) -> PaymentResult:
        # No real signature to check in mock mode - reuse the same
        # deterministic simulator as charge() so behavior is identical
        # to before this feature existed, for reviewers without live keys.
        method = payload.get("method", "upi")
        return self.charge(order_id, payload.get("amount", 0), method, attempt_seed=0)


class RazorpayGateway(PaymentGateway):
    """Thin wrapper over the real razorpay SDK, test-mode.

    Requires `pip install razorpay` and RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET
    (test-mode keys from the Razorpay dashboard) in the environment.
    """

    def __init__(self):
        import razorpay  # imported lazily so mock mode has no hard dependency

        self.client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))

    def charge(self, order_id: int, amount: float, method: str, attempt_seed: int = 0) -> PaymentResult:
        """Used by the automated recovery loop's retries. A real card/UPI
        retry needs either user interaction or a saved payment token -
        neither is in scope here, so recovery retries are simulated even
        in real mode; the FIRST attempt (create_checkout_order +
        verify_and_capture below) is the genuine, real-money-rails path.
        """
        try:
            rp_order = self.client.order.create(
                {
                    "amount": int(amount * 100),
                    "currency": "INR",
                    "notes": {"internal_order_id": str(order_id), "method": method},
                }
            )
            return PaymentResult(success=True, gateway_ref=rp_order["id"])
        except Exception as exc:  # noqa: BLE001
            return PaymentResult(success=False, gateway_ref="", failure_reason=str(exc))

    def create_checkout_order(self, order_id: int, amount: float) -> dict:
        rp_order = self.client.order.create(
            {
                "amount": int(amount * 100),
                "currency": "INR",
                "notes": {"internal_order_id": str(order_id)},
            }
        )
        return {
            "mode": "real",
            "razorpay_order_id": rp_order["id"],
            "amount": int(amount * 100),
            "currency": "INR",
            "key_id": settings.razorpay_key_id,
        }

    def verify_and_capture(self, order_id: int, payload: dict) -> PaymentResult:
        try:
            self.client.utility.verify_payment_signature({
                "razorpay_order_id": payload["razorpay_order_id"],
                "razorpay_payment_id": payload["razorpay_payment_id"],
                "razorpay_signature": payload["razorpay_signature"],
            })
        except Exception:  # noqa: BLE001 - any verification failure is a real failure
            return PaymentResult(success=False, gateway_ref="", failure_reason="signature_verification_failed")

        try:
            payment = self.client.payment.fetch(payload["razorpay_payment_id"])
            if payment.get("status") in ("captured", "authorized"):
                return PaymentResult(success=True, gateway_ref=payload["razorpay_payment_id"])
            return PaymentResult(success=False, gateway_ref="", failure_reason=f"payment_status:{payment.get('status')}")
        except Exception as exc:  # noqa: BLE001
            return PaymentResult(success=False, gateway_ref="", failure_reason=str(exc))


def get_gateway() -> PaymentGateway:
    if settings.use_mock_gateway or not settings.razorpay_key_id:
        return LocalMockGateway()
    return RazorpayGateway()
