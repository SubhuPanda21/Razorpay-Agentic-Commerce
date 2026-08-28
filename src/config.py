"""Central configuration loaded from environment variables."""
import os
from dataclasses import dataclass


@dataclass
class Settings:
    razorpay_key_id: str = os.getenv("RAZORPAY_KEY_ID", "")
    razorpay_key_secret: str = os.getenv("RAZORPAY_KEY_SECRET", "")
    use_mock_gateway: bool = os.getenv("USE_MOCK_GATEWAY", "true").lower() == "true"
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./agentic_commerce.db")

    # Risk thresholds (Track 2 - defense-only gating)
    risk_block_threshold: float = float(os.getenv("RISK_BLOCK_THRESHOLD", "0.75"))
    risk_hold_threshold: float = float(os.getenv("RISK_HOLD_THRESHOLD", "0.45"))
    velocity_window_minutes: int = int(os.getenv("VELOCITY_WINDOW_MINUTES", "10"))
    velocity_max_orders: int = int(os.getenv("VELOCITY_MAX_ORDERS", "5"))

    # Recovery bounds (Track 3 - bounded, with stopping rules)
    recovery_max_attempts: int = int(os.getenv("RECOVERY_MAX_ATTEMPTS", "3"))

    # Webhook signature verification (separate secret from API keys, set in
    # the Razorpay dashboard's webhook settings)
    razorpay_webhook_secret: str = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

    # Policy engine (hard, non-overridable business rules - distinct from risk_agent's
    # probabilistic fraud signals). No LLM/agent decision can bypass these.
    default_order_cap: float = float(os.getenv("DEFAULT_ORDER_CAP", "20000"))
    authorization_required_above: float = float(os.getenv("AUTHORIZATION_REQUIRED_ABOVE", "10000"))


settings = Settings()
