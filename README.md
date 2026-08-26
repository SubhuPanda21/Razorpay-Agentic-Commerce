<div align="center">

# 🛒 Razorpay Agentic Commerce

**An AI buyer-agent checkout system — gated by policy, scored for risk, backed by recovery, closed by reconciliation.**

Built for the Razorpay AI Buildathon · Track 01: AI Growth & Agentic Commerce

[![Python](https://img.shields.io/badge/python-3.11%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red?logo=sqlite&logoColor=white)](https://www.sqlalchemy.org/)
[![Tests](https://img.shields.io/badge/tests-11%20passing-brightgreen?logo=pytest&logoColor=white)](#tests)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](#)

[![Tests](https://img.shields.io/badge/tests-11%20passing-brightgreen?logo=pytest&logoColor=white)](#tests)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](#)

**[Live API Docs (Swagger UI)](https://razorpay-agentic-commerce-d5ii.onrender.com/docs)**


</div>

---

## The idea

Most buildathon entries pick one track and build one demo. This is **one
coherent agentic checkout pipeline** where the other three tracks aren't
separate projects — they're composed *stages* the same request flows
through. A single purchase touches product selection, hard policy rules,
probabilistic risk scoring, bounded payment recovery, and financial
reconciliation — all logged to one audit trail.

| Track | Role in this system |
|---|---|
| **01 · AI Growth & Agentic Commerce** | The primary build — the shopping agent + orchestrator |
| **02 · AI Risk Manager** | `risk_agent.py` — defense-only fraud gate (velocity + amount anomaly) |
| **03 · AI Revenue Recovery** | `recovery_agent.py` — bounded retry workflow with a stopping rule |
| **04 · AI Finance Controller** | `finance_agent.py` — reconciliation with honest exception reporting |

---

## How a purchase actually flows

```mermaid
flowchart TD
    A["🧑‍💻 Buyer Agent<br/>natural-language request"] --> B["🛍️ Shopping Agent<br/>search_catalog · check_inventory"]
    B -->|"no match / out of stock"| Z1["❌ Order rejected"]
    B -->|"product selected"| C["📝 Order Created"]

    C --> D{"⚖️ Policy Engine<br/>hard, non-overridable rules"}
    D -->|"over budget cap<br/>or missing authorization"| Z2["🚫 Policy Rejected<br/>(final — no retry)"]
    D -->|"approved"| E{"🛡️ Risk Agent<br/>velocity + amount anomaly"}

    E -->|"block"| Z3["🚫 Blocked"]
    E -->|"hold / allow"| F["💳 Payment Attempt<br/>Razorpay gateway"]

    F -->|"success"| G["✅ Paid"]
    F -->|"failure"| H["🔁 Recovery Agent<br/>bounded retries + stopping rule"]

    H -->|"recovered"| G
    H -->|"max attempts hit"| Z4["❌ Failed<br/>(escalated, not retried forever)"]

    G --> I["📊 Finance Agent<br/>reconcile expected vs settled"]
    I --> J["🧾 Audit Trail<br/>every step, one order ID"]

    style D fill:#3d2b1f,stroke:#d4a373,color:#fff
    style E fill:#2b1f1f,stroke:#e07a5f,color:#fff
    style H fill:#1f2b2b,stroke:#81b29a,color:#fff
    style I fill:#1f2433,stroke:#6d9dc5,color:#fff
    style J fill:#232323,stroke:#f2cc8f,color:#fff
```

**Why the policy engine and risk agent are two separate boxes:** the
policy engine enforces *deterministic* rules (spending caps, authorization
thresholds) that no agent or LLM can override — a rejection there is
final. The risk agent scores *probabilistic* fraud signals and can land
on "hold" for human review. Conflating the two would let a clever prompt
argue its way past a hard business rule.

---

## One request, every stage — sequence view

```mermaid
sequenceDiagram
    participant Buyer as Buyer Agent
    participant Shop as Shopping Agent
    participant Policy as Policy Engine
    participant Risk as Risk Agent
    participant Gate as Payment Gateway
    participant Rec as Recovery Agent
    participant Fin as Finance Agent
    participant Audit as Audit Trail

    Buyer->>Shop: "buy a wool throw blanket"
    Shop->>Shop: search_catalog() + check_inventory()
    Shop->>Audit: log product_selected
    Shop->>Policy: order created (₹2,499)
    Policy->>Policy: check spending cap + authorization
    Policy->>Audit: log policy_evaluated
    alt policy rejected
        Policy-->>Buyer: order rejected (final)
    else policy approved
        Policy->>Risk: proceed
        Risk->>Risk: velocity + amount z-score
        Risk->>Audit: log risk_assessed
        alt risk = block
            Risk-->>Buyer: order blocked
        else risk = allow / hold
            Risk->>Gate: initiate_payment()
            Gate-->>Risk: success or failure
            alt payment failed
                Risk->>Rec: recover(order)
                loop up to max_attempts
                    Rec->>Gate: retry (alt method)
                end
                Rec->>Audit: log recovery_attempt(s)
            end
            Rec->>Fin: reconcile(order)
            Fin->>Audit: log reconciled
            Fin-->>Buyer: order complete
        end
    end
```

---

## Repo layout

```
src/
├── config.py                settings from env
├── db/                       models.py, database.py — orders, products, risk
│                             assessments, recovery attempts, reconciliation, audit log
├── gateway/
│   └── razorpay_client.py    real razorpay-python SDK path + deterministic
│                             local mock (runs fully without live keys)
├── catalog/                  merchant catalog data + keyword search
├── tools/                    explicit, named agent tools — the agent calls
│   ├── catalog_tools.py      these, never the DB directly
│   ├── order_tools.py
│   └── payment_tools.py
├── policies/
│   └── policy_engine.py      hard, non-overridable business rules
├── agents/
│   ├── shopping_agent.py     Track 01 — product selection + reasoning
│   ├── risk_agent.py         Track 02
│   ├── recovery_agent.py     Track 03
│   ├── finance_agent.py      Track 04
│   └── orchestrator.py       thin coordinator — no business logic of its own
├── audit/                     append-only audit trail writer/reader
└── api/main.py                FastAPI app
scripts/
├── seed_data.py               loads a sample merchant + catalog
└── run_demo.py                scripted end-to-end CLI run (good for recording)
tests/                         pytest coverage for every agent, the policy
                                engine, and the full pipeline
```

---

## Running it

```bash
python -m venv venv && source venv/bin/activate   # venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env                              # copy .env.example .env on Windows

python -m scripts.seed_data     # creates the DB + sample catalog
python -m scripts.run_demo      # scripted end-to-end trace — good for recording

uvicorn src.api.main:app --reload   # or run it as a live API
Hosted instance (no frontend — this is the FastAPI backend only): Swagger UI →
```

Then, with the API running:

```bash
curl -X POST http://localhost:8000/purchase \
  -H "Content-Type: application/json" \
  -d '{"merchant_id": 1, "buyer_agent_id": "agent-001", "query": "coffee set", "budget_limit": 20000}'

curl http://localhost:8000/orders/1/audit
curl http://localhost:8000/finance/summary
```

---

## Tests

```bash
pytest -v
```

11 tests, all passing:

| Suite | Covers |
|---|---|
| `test_risk_agent.py` | allow/hold/block decisions, velocity gating |
| `test_policy_engine.py` | spending-cap rejection, authorization threshold |
| `test_recovery_agent.py` | bounded retries, the stopping rule actually stops |
| `test_finance_agent.py` | reconciliation matching + honest exception flagging |
| `test_orchestrator.py` | full pipeline end to end, out-of-stock short-circuit |

---

## Using real Razorpay test-mode keys

Set `USE_MOCK_GATEWAY=false` and provide `RAZORPAY_KEY_ID` /
`RAZORPAY_KEY_SECRET` (test-mode, from the Razorpay dashboard) in
`.env`. `src/gateway/razorpay_client.py` then creates real test-mode
orders through the official `razorpay` SDK. A production checkout also
needs the client-side checkout widget + webhook capture — the current
`RazorpayGateway.charge()` creates the server-side order and is the
integration point to wire that in.

---

## Why this shape

Track 01's own bar asks for *"every money action explainable, bounded and
gated... show the audit trail and one failure handled gracefully."*
That's satisfied directly by this pipeline: policy gates enforce hard
limits no agent can override, risk gates score probabilistic fraud
signals before spend, recovery is bounded with a real stopping rule,
reconciliation reports exceptions instead of hiding them, and the audit
trail ties every decision to one order ID from request to settlement.
