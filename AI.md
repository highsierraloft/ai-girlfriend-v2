Below is the revised AI.md — cleaner, tighter, and 100 % aligned with the spec you just gave.
Copy-paste it into the repo root (or into docs/ if that’s your convention) and let Cursor do its thing.

⸻


# AI-Girlfriend Telegram Bot

> **Status:** MVP design phase — last updated: 2025-06-20  
> **Owner:** Herman

A Telegram bot that role-plays **Alice** — a cheeky, slightly bratty e-girl.  
**Spice8B** (self-hosted on Hugging Face) handles the dialogue; users pay “loans” (credits) to keep chatting.  
No embeddings, no vector search — we simply feed the model **base-prompt + user-profile + chat history** until we hit the 8 k-token context limit.

---

## ⚡ TL;DR

* **MVP in ≤ 2 months**, dockerised, <$10 k CAPEX.  
* **Start pack:** 10 free loans per user, +10 every day at 22:00 Europe/Kyiv.  
* **Credits = messages.** One loan → one reply from the model.  
* Age-gate (18 +) with inline keyboard.  
* PostgreSQL persists everything; Redis caches recent history; APScheduler tops up loans nightly.  
* Payments via **₴ / ₽ / ₺ / crypto** (gateways TBD in Phase 2).  
* Phase 2 also adds erotic image generation & backup censored model.

---

## 1 · Project Goals

| KPI | Target |
|-----|--------|
| **Shipping** | MVP live in 8 weeks |
| **Daily Active Users** | ≥ 1 000 |
| **Paid Conversion** | ≥ 7 % |
| **Variable Cost** | ≤ $0.05 / engaged user |
| **Content class** | C2 erotic (no minors, bestiality, gore) |

---

## 2 · High-Level Architecture

┌──────────────┐        ┌────────────────────────┐        ┌───────────────────┐
│   Telegram   │◄──────►│ Bot Webhook (FastAPI)  │◄──────►│  Redis (cache)    │
└──────────────┘        │  • python-telegram-bot │        └───────────────────┘
│  • Scheduler (APSched) │
└──────────┬─────────────┘
│HTTP
┌──────────▼─────────────┐
│  Spice8B @ HuggingFace │
│  (text generation)     │
└──────────┬─────────────┘
│async-pg
┌──────────▼─────────────┐
│ PostgreSQL (RDS / self)│
│  • user_profile        │
│  • message_log         │
└────────────────────────┘

_All inference runs on Hugging Face; the bot server is CPU-only._

---

## 3 · Tech Stack

| Layer | Choice & Rationale |
|-------|--------------------|
| **Bot Framework** | [`python-telegram-bot v20`](https://docs.python-telegram-bot.org/) (async) |
| **Backend** | `FastAPI` + `uvicorn` |
| **LLM** | **Spice8B** (fork of Llama 2 8B) — chat template requires `<|im_start|>` / `<|im_end|>` delimiters  [oai_citation:0‡community.openai.com](https://community.openai.com/t/what-do-the-im-start-and-im-end-tokens-mean/145727?utm_source=chatgpt.com) |
| **DB** | PostgreSQL 16 |
| **Cache / Rate-limit** | Redis |
| **Scheduler** | APScheduler |
| **Container** | `python:3.12-slim` → multi-stage docker; app starts with `python -m bot` |
| **Testing** | `pytest` (loan logic, age-gate, token-budget) |
| **Logging** | STDOUT JSON; can be scraped by Loki / Promtail later |
| **Payments** | TBD — placeholder handlers for ₴ MonoPay, ₽ YooMoney, ₺ PayTR, crypto (UTORG) |

---

## 4 · Prompt Strategy

Spice8B follows **ChatML**:

```text
<|im_start|>system
You are Alice, a playful...
<|im_end|>
<|im_start|>user
Hi!
<|im_end|>
<|im_start|>assistant

Prompt budget: 8 000 tokens (Spice8B max context).
	1.	Base prompt — persona & style.
	2.	User profile — free-text preferences (stored in user_profile.preference).
	3.	Chat history — all messages after last_reset_at, newest first, until we hit the limit.
	4.	Assistant prefix (<|im_start|>assistant\n) to get the reply.

Token counting uses the model’s own tokenizer (loaded once at startup).
If the combined prompt > 8 000 tokens, we truncate the oldest messages.

⸻

5 · Menu & Commands

Command / Button	Action
Profile	Show current profile prefs & allow editing
Loans	Display remaining loans
Top-up	Inline buttons: ₴ / ₽ / ₺ / Crypto (opens payment URL)
About	Usage tips (asterisks = actions, plain = dialogue)
Dev Group	Jump to t.me/YourDevGroup
/reset	Sets last_reset_at = NOW; future prompts ignore older history
Age-gate (inline)	“I’m 18” ✅ unlocks chat, “I’m < 18” 🚫 = goodbye


⸻

6 · Credit System (“Loans”)
	•	Table user_profile.loan_balance (int).
	•	New user → loan_balance = 10.
	•	Each assistant reply decrements by 1.
	•	If zero: bot replies “Out of loans — top-up or wait for daily refill”.
	•	Scheduler job (Europe/Kyiv, 22:00 daily)

UPDATE user_profile SET loan_balance = loan_balance + 10;



⸻

7 · Data Model (minimal)

erDiagram
  user_profile {
    bigint id PK
    bigint chat_id UNIQUE
    timestamptz created_at
    text preference
    int loan_balance
    timestamptz last_reset_at
  }
  message_log {
    bigint id PK
    bigint chat_id FK
    text role  -- 'user' | 'assistant'
    text content
    timestamptz created_at
  }
  user_profile ||--|{ message_log : "has"

Index on message_log.chat_id, created_at for fast fetch.

⸻

8 · Configuration

env file (loaded by Pydantic BaseSettings):

TELEGRAM_TOKEN=...
HF_ENDPOINT=https://api-inference.huggingface.co/models/your-org/spice8b
HF_API_KEY=...
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
REDIS_URL=redis://localhost:6379/0
SCHEDULE_TIMEZONE=Europe/Kyiv
FREE_DAILY_LOANS=10


# --- rate limits ---
RATE_LIMIT_PER_USER_SEC=3        # 1 msg / N seconds
HF_MAX_RPS=5                     # global cap towards Spice8B
SCHEDULE_TIMEZONE=Europe/Kyiv
FREE_DAILY_LOANS=10

All prompts, temperatures etc. live in /app/config/prompts.py so ops can tweak without code edits.

⸻

9 · Setup & Local Dev

# 1. clone fork of python-telegram-bot-base
git clone https://github.com/your-org/ai-girlfriend.git && cd ai-girlfriend

# 2. env vars
cp .env.example .env && nano .env

# 3. start infra
docker compose up -d postgres redis

# 4. run migrations (simple SQL, no Alembic)
psql -f scripts/schema.sql

# 5. launch bot
docker compose up bot

No Alembic: schema changes = new SQL file in scripts/migrations/ executed on deploy.

⸻

10 · Testing

pytest -q

	•	Loan debit / refill
	•	Age-gate lock
	•	Prompt builder respects 8 k tokens
	•	/reset slices history correctly

⸻

11 · Deployment
	•	Container: single image, < 300 MB.
	•	Runtime: any Docker host (Hetzner Cloud / Fly.io / AWS Fargate).
	•	Expose /webhook behind HTTPS (nginx or Cloudflare Tunnel).
	•	Use Telegram “self-signed certificate” option if needed.

CI pipeline (GitHub Actions):
	1.	Lint → Unit tests → Build image → Push :latest
	2.	SSH into host, docker pull && docker compose up -d --force-recreate

⸻

12 · Roadmap (Phase 2)

Feature	Notes
Erotic image generation	SDXL LoRA on Replicate; cost paid in loans (10 credits per image)
Backup censored model	Fireworks endpoint; switch via /settings
Voice replies	TTS (Coqui) streamed as OGG
Payment gateways	Implement real SDKs & webhook handlers
Observability	Prometheus + Grafana Cloud, Sentry tracing


⸻

13 · License

MIT — you must be ≥ 18 y o to use this bot.

⸻

Reality check: external NSFW APIs can disappear overnight; keep self-host fallback scripts handy.

### How this differs from the previous draft

* Cut embeddings, pgvector, and image generation from the MVP path.  
* Replaced Llama-3 + Fireworks with **Spice8B on Hugging Face** and documented its `<|im_start|>` / `<|im_end|>` chat template.  
* Added **loans** system, daily scheduler top-up, age-gate UX, `/reset` logic, and full message retention in PostgreSQL.  
* Swapped Alembic for plain SQL migrations (simpler).  
* Docker-centric deploy with minimal unit-test harness.  
* Stubbed out payments & Phase-2 roadmap.

Kick the tyres; if something’s still off, shout and we’ll tweak.