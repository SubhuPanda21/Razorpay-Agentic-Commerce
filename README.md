# Razorpay Agentic Commerce

An AI buyer-agent checkout system built for the Razorpay AI Buildathon.

**Primary track: Track 01 — AI Growth & Agentic Commerce.**
One agentic purchase flow that also incorporates Track 02 (risk gating),
Track 03 (recovery), and Track 04 (reconciliation) as composed stages of
the same pipeline — not four separate demos.

## What it does

An AI buyer agent sends a natural-language purchase request. The system:

1. **Shopping agent selects a product** (Track 1) via explicit tools
   (`search_catalog`, `check_inventory`) — never touching the DB directly.
2. **Policy engine enforces hard, non-overridable rules** — spending
   caps and an authorization threshold for high-value orders. This is
   deliberately separate from risk scoring: a policy rejection is final,
   the flow never "retries around" it the way it retries around a
   payment failure. No agent or LLM can talk its way past this layer.
3. **Risk agent gates the order** (Track 2) — velocity + amount-anomaly
   scoring, strictly defense-only (allow / hold / block, never an
   offensive action).
4. **Payment is attempted** through a Razorpay-compatible gateway interface.
5. **On failure, a bounded recovery workflow runs** (Track 3) — retries
   with an alternate payment method, capped at a max attempt count with
   an explicit stopping rule.
6. **The settled transaction is reconciled** (Track 4) — matches expected
   vs settled amount, and reports honest exceptions instead of hiding
   them.
7. **Every step writes to a shared, append-only audit trail** — the
   whole run is explainable end to end, per Track 1's own bar.

## Architecture

```
src/
  config.py           settings from env
  db/                 SQLAlchemy models + session (orders, products,
                       risk assessments, recovery attempts, reconciliation,
                       audit log)
  gateway/             razorpay_client.py — real razorpay-python SDK path
                       + a deterministic local mock so the whole thing
                       runs without live keys
  catalog/             merchant catalog data + search
  tools/               explicit, named agent tools — search_catalog,
                       check_inventory, create_order, initiate_payment.
                       The agent calls these, never the DB directly.
  policies/            policy_engine.py — hard business rules (spending
                       cap, authorization threshold) an agent can never
                       override. Distinct from risk_agent's probabilistic
                       fraud scoring.
  agents/
    shopping_agent.py   Track 1 — product selection + reasoning
    risk_agent.py        Track 2
    recovery_agent.py    Track 3
    finance_agent.py     Track 4
    orchestrator.py       thin coordinator — sequences the above,
                         holds no business logic itself
  audit/               append-only audit trail writer/reader
  api/main.py          FastAPI app
scripts/
  seed_data.py         loads a sample merchant + catalog
  run_demo.py          scripted end-to-end CLI run for the demo video
tests/                 pytest coverage for every agent, the policy
                       engine, and the full flow
```

## Running it

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

python -m scripts.seed_data     # creates the DB + sample catalog
python -m scripts.run_demo      # scripted end-to-end trace (good for recording)

uvicorn src.api.main:app --reload   # or run it as a live API
```

Then, with the API running:

```bash
curl -X POST http://localhost:8000/purchase \
  -H "Content-Type: application/json" \
  -d '{"merchant_id": 1, "buyer_agent_id": "agent-001", "query": "coffee set", "budget_limit": 20000}'

curl http://localhost:8000/orders/1/audit
curl http://localhost:8000/finance/summary
```

## Tests

```bash
pytest -v
```

Covers: risk gate decisions (allow/hold/block), the policy engine's
spending-cap and authorization-threshold rules, the recovery loop's
stopping rule, reconciliation matching + exception flagging, and the
full checkout pipeline end to end.

## Using real Razorpay test-mode keys

Set `USE_MOCK_GATEWAY=false` and provide `RAZORPAY_KEY_ID` /
`RAZORPAY_KEY_SECRET` (test-mode, from the Razorpay dashboard) in
`.env`. `src/gateway/razorpay_client.py` then creates real test-mode
orders through the official `razorpay` SDK. A production checkout also
needs the client-side checkout widget + webhook capture — the current
`RazorpayGateway.charge()` creates the server-side order and is the
integration point to wire that in.

## Why this shape

Track 1's own bar asks for "every money action explainable, bounded and
gated... show the audit trail and one failure handled gracefully."
That's satisfied directly by this pipeline: risk gates before spend,
recovery is bounded with a stopping rule, reconciliation reports
exceptions instead of hiding them, and the audit trail ties every
decision to one order ID.
