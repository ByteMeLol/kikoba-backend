# VICOBA / Kikoba Backend API

A high-performance, asynchronous REST API service for **VICOBA (Village Community Banking)** and community savings groups (Chamas / SACCOs), built strictly to the specifications in `backend-docu.pdf`.

---

## 🛠 Tech Stack

As specified in the official specification document:
- **Framework:** FastAPI (Python 3.11+)
- **Database:** PostgreSQL
- **ORM:** SQLAlchemy (Async)
- **Migrations:** Alembic
- **Validation & Serialization:** Pydantic v2
- **Authentication:** JWT (JSON Web Tokens) with PIN/OTP verification
- **Task Management:** FastAPI `BackgroundTasks` / Celery (for SMS gateways)
- **API Documentation:** Interactive Swagger UI (`/docs`) & ReDoc (`/redoc`)

---

## 🏗 System Architecture & Key Concepts

1. **Async Performance:** Uses native Python `async/await` for high-throughput, non-blocking I/O—critical when waiting for external Mobile Money USSD push responses and webhook callbacks.
2. **Shadow Profiles:** Group admins can register members on the group ledger using just a phone number and name before the member even registers on the app. When that person registers, their shadow profile is linked and activated.
3. **Maker-Checker Security:** High-impact financial actions (such as approving loans and closing cycles for dividend share-outs) require multi-admin signatures and PIN confirmations.
4. **Meeting-Centric Ledger:** Financial operations (share purchases, social funds, fines) are linked to weekly/monthly meeting sessions.
5. **ACID Transaction Isolation:** Share purchases, loan disbursements, and repayments are executed in isolated database transactions to prevent race conditions.

---

## 🗺 Step-by-Step Implementation Roadmap

Follow this step-by-step roadmap to build the backend from ground zero to production:

```
[Phase 1: Foundation & Setup]
          │
          ▼
[Phase 2: Database Models & Migrations]
          │
          ▼
[Phase 3: Auth & Member Passbook]
          │
          ▼
[Phase 4: Groups, Members & Meetings]
          │
          ▼
[Phase 5: Financial Operations & Loans]
          │
          ▼
[Phase 6: Webhooks & Payment Integration]
          │
          ▼
[Phase 7: Cycle Closure & Share-out]
          │
          ▼
[Phase 8: Testing, Docker & Deployment]
```

---

### Step 1: Project Scaffolding & Environment Setup
- [ ] Initialize Python virtual environment: `python3 -m venv .venv && source .venv/bin/activate`
- [ ] Install core dependencies:
  - `fastapi`, `uvicorn[standard]`
  - `sqlalchemy`, `asyncpg`, `alembic`
  - `pydantic`, `pydantic-settings`
  - `python-jose[cryptography]`, `passlib[bcrypt]`
  - `httpx` (for calling Mobile Money / SMS APIs asynchronously)
- [ ] Establish standard directory structure:
  ```text
  kikoba-backend/
  ├── app/
  │   ├── api/
  │   │   └── v1/
  │   │       ├── endpoints/
  │   │       │   ├── auth.py
  │   │       │   ├── users.py
  │   │       │   ├── groups.py
  │   │       │   ├── meetings.py
  │   │       │   ├── transactions.py
  │   │       │   ├── loans.py
  │   │       │   ├── social_fund.py
  │   │       │   ├── cycles.py
  │   │       │   └── webhooks.py
  │   │       └── router.py
  │   ├── core/
  │   │   ├── config.py         # Pydantic Settings (.env)
  │   │   ├── security.py       # JWT & PIN hashing
  │   │   └── exceptions.py     # Global error handlers (400, 401, 403, 404, 409, 422, 500)
  │   ├── db/
  │   │   ├── base.py           # SQLAlchemy declarative base
  │   │   └── session.py        # Async engine & sessionmaker
  │   ├── models/               # SQLAlchemy ORM models
  │   ├── schemas/              # Pydantic request/response schemas
  │   └── services/             # Business logic (SMS, payments, dividend math)
  ├── alembic/                  # Database migration scripts
  ├── alembic.ini
  ├── .env.example
  ├── requirements.txt
  └── README.md
  ```
- [ ] Configure global error handling strategy:
  - `400`: Business rule violations (e.g., loan > 3x shares, shares > max limit)
  - `401`: Unauthorized / invalid JWT
  - `403`: Forbidden (e.g., regular member trying to close a cycle)
  - `404`: Resource not found
  - `409`: Conflict (phone already registered, duplicate transaction reference)
  - `422`: Automatic Pydantic payload validation error

---

### Step 2: Database Schema & Migrations (SQLAlchemy & Alembic)
- [ ] **Users Table (`users`)**:
  - `id`, `phone_number` (unique), `full_name`, `national_id`, `hashed_pin`, `status` (`active`, `shadow`), `kyc_verified` (boolean), `created_at`.
- [ ] **Groups Table (`groups`)**:
  - `id`, `name`, `share_value`, `max_shares_per_meeting`, `interest_rate_monthly`, `meeting_frequency` (`weekly`/`monthly`), `created_by`, `status`.
- [ ] **Group Memberships Table (`group_members`)**:
  - `id`, `group_id`, `user_id`, `role` (`chairperson`, `treasurer`, `secretary`, `member`), `joined_at`.
- [ ] **Cycles Table (`cycles`)**:
  - `id`, `group_id`, `cycle_number`, `start_date`, `end_date`, `status` (`active`, `closed`), `total_profit_distributed`, `dividend_per_share`.
- [ ] **Meetings Table (`meetings`)**:
  - `id`, `group_id`, `cycle_id`, `scheduled_date`, `status` (`scheduled`, `in_progress`, `completed`).
- [ ] **Attendance & Fines Table (`attendance`, `fines`)**:
  - Attendance: `meeting_id`, `member_id`, `status` (`present`, `late`, `absent`).
  - Fines: `member_id`, `meeting_id`, `amount`, `reason`, `is_paid`.
- [ ] **Transactions Table (`transactions`)**:
  - `id`, `reference_id`, `group_id`, `member_id`, `meeting_id`, `type` (`share_purchase`, `social_fund`, `fine_payment`, `loan_repayment`), `amount`, `shares_count`, `status` (`pending`, `success`, `failed`).
- [ ] **Loans Table (`loans`)**:
  - `id`, `group_id`, `member_id`, `amount`, `purpose`, `duration_months`, `interest_rate`, `status` (`pending_approval`, `disbursed`, `repaid`, `defaulted`), `payout_reference`.
- [ ] **Social Fund Claims Table (`social_fund_claims`)**:
  - `id`, `group_id`, `member_id`, `amount`, `reason`, `status` (`pending_group_approval`, `approved`, `rejected`).
- [ ] Run initial migration: `alembic revision --autogenerate -m "initial_schema"` followed by `alembic upgrade head`.

---

### Step 3: Authentication & Passbook
- [ ] Implement `POST /api/v1/auth/register`:
  - Verify if phone number exists.
  - If a **shadow profile** exists, upgrade status to `active`, store National ID and hashed PIN.
  - If already active, return `409 Conflict`.
  - Issue 4-digit OTP via reference ID.
- [ ] Implement `POST /api/v1/auth/request-otp`:
  - Check phone number exists & active. Generate OTP, return `reference_id`.
- [ ] Implement `POST /api/v1/auth/verify`:
  - Validate OTP against `reference_id`. Return JWT bearer access token.
- [ ] Implement `GET /api/v1/users/me` (Digital Passbook):
  - Return KYC status, active groups, total shares count, total share value, social fund balance, and active loan repayment summary.

---

### Step 4: Group & Meeting Management
- [ ] Implement `POST /api/v1/groups`:
  - Create group and automatically initialize Cycle 1.
  - Designate authenticated creator as `chairperson`.
- [ ] Implement `POST /api/v1/groups/{group_id}/members`:
  - Admin adds member by phone.
  - If user is not yet in the system, create a **shadow profile** (`status='shadow'`) and queue an SMS invite using FastAPI `BackgroundTasks`.
- [ ] Implement `GET /api/v1/groups/{group_id}/members`:
  - Return master ledger of all group members and their current financial standing.
- [ ] Implement `POST /api/v1/groups/{group_id}/meetings`:
  - Open new meeting ledger for scheduled date.
- [ ] Implement `POST /api/v1/groups/{group_id}/meetings/{meeting_id}/attendance`:
  - Record attendees; automatically calculate and persist fines for late and absent members.

---

### Step 5: Financial Operations (Shares, Loans & Social Fund)
- [ ] Implement `POST /api/v1/groups/{group_id}/transactions/deposit`:
  - Validate: `shares_bought <= max_shares_per_meeting` (return `400 Bad Request` if exceeded).
  - Calculate total amount (`shares_bought * share_value + social_fund_amount`).
  - Create pending transaction record and trigger mock/real USSD Push.
- [ ] Implement `POST /api/v1/groups/{group_id}/loans/apply`:
  - Business rule: validate that requested amount does not exceed `3 * member_total_shares * share_value`.
  - Set status to `pending_approval`.
- [ ] Implement `POST /api/v1/groups/{group_id}/loans/{loan_id}/approve`:
  - Require maker-checker admin PIN validation.
  - Trigger B2C Mobile Money payout and mark status as `disbursed`.
- [ ] Implement `POST /api/v1/groups/{group_id}/loans/{loan_id}/repay`:
  - Initiate USSD push for member loan installment.
- [ ] Implement `POST /api/v1/groups/{group_id}/social-fund/claim`:
  - Submit emergency medical/bereavement assistance claim.

---

### Step 6: Webhooks & Payment Gateway Callbacks
- [ ] Implement `POST /api/v1/webhooks/payments`:
  - Endpoint for Selcom / ClickPesa / Mobile Money callbacks.
  - Verify webhook signature / token.
  - If status is `SUCCESS`:
    - Mark transaction as completed.
    - If share purchase: update member's cumulative shares.
    - If loan repayment: deduct from loan principal & interest ledger.
    - Trigger background task to send SMS receipt to member.

---

### Step 7: Cycle Closure & Share-Out (Gawio)
- [ ] Implement `POST /api/v1/groups/{group_id}/cycles/{cycle_id}/close`:
  - Validate multi-admin approval: verify array of `admin_signatures` and confirmation PIN.
  - Calculate total profit: `Sum of all loan interest collected + all fines collected`.
  - Calculate dividend per share: `total_profit / total_shares_in_group`.
  - Calculate each member's payout: `(member_shares * share_value) + (member_shares * dividend_per_share)`.
  - Lock cycle and initiate automated payouts.

---

### Step 8: Testing, Docker & Deployment
- [ ] Write integration tests for:
  - Auth & shadow profile claiming.
  - Loan eligibility constraints (<= 3x shares).
  - Webhook callback reconciliation.
  - Cycle dividend distribution math.
- [ ] Create `Dockerfile` and `docker-compose.yml` for FastAPI + PostgreSQL.
- [ ] Verify automatic OpenAPI Swagger documentation at `http://localhost:8000/docs`.

---

## 🚦 Where We Start First: Immediate Next Step

We start at **Step 1 & Step 2**:
1. **Initialize the Python virtual environment** and install the core dependencies (`fastapi`, `uvicorn`, `sqlalchemy`, `alembic`, `pydantic-settings`, `asyncpg`/`psycopg2`).
2. **Set up the base project structure** with configuration and database connection.
3. **Build the database models** (`User`, `Group`, `GroupMember`, `Meeting`, `Transaction`, `Loan`, `Fine`) so the rest of the endpoints have a solid, consistent data layer.
