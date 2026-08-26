"""End-to-end CLI demo - good for screen-recording.

Runs several purchases through the full pipeline (including a
recovery-path order and a risk-blocked order) and prints a readable
trace of every agent decision.

Run: python -m scripts.run_demo
"""
from src.db.database import SessionLocal, init_db
from src.db.models import Merchant
from src.agents.orchestrator import run_checkout


def line(title: str):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def print_trail(trail):
    for step in trail:
        print(f"  [{step['actor']:>16}] {step['action']:<22} {step['detail']}")


def main():
    init_db()
    db = SessionLocal()
    merchant = db.query(Merchant).first()
    if not merchant:
        print("No merchant found - run `python -m scripts.seed_data` first.")
        return

    line("SCENARIO 1: Normal purchase (likely happy path or one retry)")
    result = run_checkout(db, merchant.id, "buyer-agent-001", "coffee set for the kitchen")
    print(f"Result: {result.status} - {result.message}")
    print_trail(result.audit_trail)

    line("SCENARIO 2: Same buyer, rapid-fire orders -> risk gate should react")
    for i in range(6):
        result = run_checkout(db, merchant.id, "buyer-agent-002", "desk organizer")
        print(f"  order {i+1}: status={result.status}")
    print("Last order's full trail:")
    print_trail(result.audit_trail)

    line("SCENARIO 3: High-value order vs merchant history -> anomaly check")
    result = run_checkout(db, merchant.id, "buyer-agent-003", "wool throw blanket", quantity=2)
    print(f"Result: {result.status} - {result.message}")
    print_trail(result.audit_trail)

    line("SCENARIO 4: Policy engine hard-rejects an over-budget order (no override possible)")
    result = run_checkout(db, merchant.id, "buyer-agent-004", "wool throw blanket", budget_limit=1000)
    print(f"Result: {result.status} - {result.message}")
    print_trail(result.audit_trail)

    line("FINANCE SUMMARY")
    from src.agents.finance_agent import summary
    print(summary(db))

    db.close()


if __name__ == "__main__":
    main()
