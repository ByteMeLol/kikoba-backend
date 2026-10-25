# VICOBA / Kikoba Backend API

A high-performance, asynchronous REST API service for **VICOBA (Village Community Banking)** and community savings groups (Chamas / SACCOs), built strictly to the specifications in `backend-docu.pdf`.

---

## 🛠 Tech Stack

As specified in the official specification document:
- **Framework:** FastAPI (Python 3.11+)
- **Database:** PostgreSQL (with `asyncpg`)
- **ORM:** SQLAlchemy 2.0 (Async)
- **Migrations:** Alembic
- **Validation & Serialization:** Pydantic v2
- **Authentication:** JWT (JSON Web Tokens) with PIN/OTP verification & bcrypt hashing
- **Task Management:** FastAPI `BackgroundTasks` (for SMS gateways & USSD push)
- **API Documentation:** Interactive Swagger UI (`/docs`) & ReDoc (`/redoc`)
- **Containerization:** Docker & Docker Compose

---

## 🏗 System Architecture & Key Concepts

1. **Async Performance:** Uses native Python `async/await` for high-throughput, non-blocking I/O—critical when waiting for external Mobile Money USSD push responses and webhook callbacks.
2. **Shadow Profiles:** Group admins can register members on the group ledger using just a phone number and name before the member even registers on the app. When that person registers, their shadow profile is linked and activated.
3. **Maker-Checker Security:** High-impact financial actions (such as approving loans and closing cycles for dividend share-outs) require multi-admin signatures and PIN confirmations.
4. **Meeting-Centric Ledger:** Financial operations (share purchases, social funds, fines) are linked to weekly/monthly meeting sessions.
5. **ACID Transaction Isolation:** Share purchases, loan disbursements, and repayments are executed in isolated database transactions to prevent race conditions.

---

## 🗺 Implementation Checklist (Status: Complete ✅)

```
[Phase 1: Foundation & Setup]          ✅ Completed
          │
          ▼
[Phase 2: Database Models & Migrations]  ✅ Completed
          │
          ▼
[Phase 3: Auth & Member Passbook]       ✅ Completed
          │
          ▼
[Phase 4: Groups, Members & Meetings]   ✅ Completed
          │
          ▼
[Phase 5: Financial Operations & Loans] ✅ Completed
          │
          ▼
[Phase 6: Webhooks & Payment Gateways]  ✅ Completed
          │
          ▼
[Phase 7: Cycle Closure & Share-out]    ✅ Completed
          │
          ▼
[Phase 8: Testing, Docker & Deployment] ✅ Completed
```

---

### Step 1: Project Scaffolding & Environment Setup ✅
- [x] Virtual environment and dependencies (`fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `alembic`, `pydantic v2`, `pydantic-settings`, `python-jose`, `passlib`, `bcrypt`, `httpx`).
- [x] Standard modular directory structure (`app/core`, `app/api/v1`, `app/models`, `app/services`, `app/db`).
- [x] Global error handling strategy implemented in [`app/core/exceptions.py`](file:///Users/user/projects/kikoba-backend/app/core/exceptions.py) matching the specification (`400`, `401`, `403`, `404`, `409`, `422`, `500`).

---

### Step 2: Database Schema & Migrations ✅
- [x] **Users & Shadow Profiles** (`users`, `otp_verifications`): phone, full name, national ID, hashed PIN, status (`active`/`shadow`), KYC verified.
- [x] **Groups, Members & Cycles** (`groups`, `group_members`, `cycles`): bylaws, share values, maximum shares per meeting, monthly interest rate, meeting frequency, and member roles (`chairperson`, `treasurer`, `secretary`, `member`).
- [x] **Meetings, Attendance & Fines** (`meetings`, `attendances`, `fines`): meeting ledger sessions, attendance tracking (`present`, `late`, `absent`), and automatic fine generation.
- [x] **Transactions** (`transactions`): deposits, share purchases, social funds, loan repayments, and dividend payouts.
- [x] **Loans** (`loans`): principal, interest calculation, Maker-Checker admin approval, disbursement status, and repayment balance.
- [x] **Social Fund Claims** (`social_fund_claims`): emergency assistance workflow.
- [x] Alembic migration configuration in [`alembic/env.py`](file:///Users/user/projects/kikoba-backend/alembic/env.py).

---

### Step 3: Authentication & Digital Passbook ✅
- [x] `POST /api/v1/auth/register`: Phone registration with shadow profile claiming logic and 409 conflict checks.
- [x] `POST /api/v1/auth/request-otp`: OTP generation with SMS background dispatch and reference ID.
- [x] `POST /api/v1/auth/verify`: OTP verification, reference invalidation, and JWT token issuance.
- [x] `GET /api/v1/users/me`: Authenticated digital passbook calculation (shares, share value total, social fund balance, active loans).

---

### Step 4: Group & Meeting Management ✅
- [x] `POST /api/v1/groups`: Create group, automatically initialize Cycle 1, and assign creator as Chairperson.
- [x] `POST /api/v1/groups/{group_id}/members`: Group admin invites member; creates shadow profile if unregistered and dispatches SMS invitation.
- [x] `GET /api/v1/groups/{group_id}/members`: Master group ledger with live standings.
- [x] `POST /api/v1/groups/{group_id}/meetings`: Starts a meeting session linked to the active cycle.
- [x] `POST /api/v1/groups/{group_id}/meetings/{meeting_id}/attendance`: Marks attendance and automatically issues fines for late and absent members.

---

### Step 5: Financial Operations (Shares, Loans & Social Fund) ✅
- [x] `POST /api/v1/groups/{group_id}/transactions/deposit`: Validates `max_shares_per_meeting` constraint (`400 Bad Request` if exceeded) and initiates USSD Push (`202 Accepted`).
- [x] `POST /api/v1/groups/{group_id}/loans/apply`: Validates 3x total share value limit (`400 Bad Request` if exceeded) and calculates loan interest and total due.
- [x] `POST /api/v1/groups/{group_id}/loans/{loan_id}/approve`: Maker-Checker admin approval requiring admin PIN validation and B2C payout reference dispatch.
- [x] `POST /api/v1/groups/{group_id}/loans/{loan_id}/repay`: Initiates USSD push for loan repayment.
- [x] `POST /api/v1/groups/{group_id}/social-fund/claim`: Submits emergency social fund claims.

---

### Step 6: Payment Webhooks & Async Reconciliation ✅
- [x] `POST /api/v1/webhooks/payments`: Selcom/ClickPesa callback listener.
- [x] Idempotent processing with status updates for shares and loan repayments.
- [x] Automatically triggers background SMS receipts to members.

---

### Step 7: Cycle Closure & Share-Out (Gawio) ✅
- [x] `POST /api/v1/groups/{group_id}/cycles/{cycle_id}/close`:
  - Validates multi-admin signatures (`admin_signatures` array + PIN).
  - Sums all loan interest and fines collected during the cycle.
  - Calculates proportional dividend per share (`total_profit / total_shares`).
  - Generates member payout records: `(shares * share_value) + (shares * dividend_per_share)`.
  - Locks cycle (`status='closed'`).

---

### Step 8: Testing & Deployment ✅
- [x] 15 comprehensive automated integration tests passing (`pytest`).
- [x] `Dockerfile` and `docker-compose.yml` for containerized PostgreSQL + FastAPI deployment.

---

## 🧪 Running Tests

```bash
source .venv/bin/activate
pytest -v
```

All 15 tests covering authentication, shadow profiles, group RBAC, meetings, fines, deposits, 3x loan validation, Maker-Checker PIN approval, webhooks, and dividend math pass with 100% success.

---

## 🚀 Running the Application

### Option A: Local Development
```bash
# 1. Activate virtual environment
source .venv/bin/activate

# 2. Run server
uvicorn app.main:app --reload --port 8000
```
Visit **`http://localhost:8000/docs`** for interactive Swagger UI documentation.

### Option B: Docker Compose (with PostgreSQL)
```bash
docker-compose up --build
```
This spins up PostgreSQL and the FastAPI application connected via `asyncpg`.
