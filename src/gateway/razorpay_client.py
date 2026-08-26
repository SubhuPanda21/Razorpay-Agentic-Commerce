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


class RazorpayGateway(PaymentGateway):
    """Thin wrapper over the real razorpay SDK, test-mode.

    Requires `pip install razorpay` and RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET
    (test-mode keys from the Razorpay dashboard) in the environment.
    """

    def __init__(self):
        import razorpay  # imported lazily so mock mode has no hard dependency

        self.client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))

    def charge(self, order_id: int, amount: float, method: str, attempt_seed: int = 0) -> PaymentResult:
        try:
            # Razorpay orders API expects amount in paise.
            rp_order = self.client.order.create(
                {
                    "amount": int(amount * 100),
                    "currency": "INR",
                    "notes": {"internal_order_id": str(order_id), "method": method},
                }
            )
            # NOTE: a real end-to-end charge also requires client-side
            # checkout + payment capture/webhook; this creates the
            # order server-side so the rest of the pipeline (risk,
            # recovery, reconciliation) has a real Razorpay order to
            # attach to. Swap in payment.capture() once you have a
            # payment_id from the checkout widget/webhook.
            return PaymentResult(success=True, gateway_ref=rp_order["id"])
        except Exception as exc:  # noqa: BLE001
            return PaymentResult(success=False, gateway_ref="", failure_reason=str(exc))


def get_gateway() -> PaymentGateway:
    if settings.use_mock_gateway or not settings.razorpay_key_id:
        return LocalMockGateway()
    return RazorpayGateway()
