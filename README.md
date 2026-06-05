# Expense Tracker API

A secure, well-structured REST API for personal expense tracking. Built with **Flask + SQLAlchemy + SQLite**, featuring JWT authentication, full CRUD, filtering/pagination, analytics, and live Swagger docs.

---

## Tech Stack & Rationale

| Layer | Choice | Why |
|---|---|---|
| Framework | Flask 3.x | Lightweight, minimal boilerplate, fast to reason about |
| Database | SQLite + SQLAlchemy ORM | Zero-setup for local dev; swap to PostgreSQL for production via one env var |
| Auth | Flask-JWT-Extended | Battle-tested JWT library; supports access + refresh tokens + revocation blocklist |
| Password hashing | Flask-Bcrypt | Industry standard; bcrypt is intentionally slow to resist brute force |
| Docs | Flasgger (Swagger 2.0) | Auto-generates `/docs` UI from docstrings; no code duplication |
| Rate limiting | Flask-Limiter | In-memory by default; pluggable storage backend for production |

---

## Project Structure

```
expense-tracker/
├── app/
│   ├── __init__.py          # App factory, extensions, JWT callbacks
│   ├── models/
│   │   └── __init__.py      # User, Category, Transaction, TokenBlocklist
│   ├── routes/
│   │   ├── auth.py          # /api/auth/*
│   │   ├── users.py         # /api/users/*
│   │   ├── categories.py    # /api/categories/*
│   │   ├── transactions.py  # /api/transactions/*
│   │   └── analytics.py     # /api/analytics/*
│   └── utils/
│       ├── responses.py     # success_response / error_response helpers
│       └── validators.py    # Input validation helpers
├── tests/
│   └── test_api.py          # 23 integration tests
├── config.py                # Config class (reads .env)
├── run.py                   # Entrypoint
├── seed.py                  # Sample data seeder
├── requirements.txt
└── .env.example
```

---

## Local Setup

### 1. Clone & install

```bash
git clone <your-repo-url>
cd expense-tracker
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and set strong values for SECRET_KEY and JWT_SECRET_KEY
```

### 3. Run the server

```bash
python run.py
```

Server starts at **http://localhost:5000**  
Swagger docs at **http://localhost:5000/docs**

> The database (`expense_tracker.db`) and default categories are created automatically on first run. No migrations needed.

### 4. (Optional) Seed sample data

```bash
python seed.py
```

Creates two users (`alice@example.com` / `bob@example.com`, password: `password123`) with 60 random transactions each.

### 5. Run tests

```bash
pytest tests/ -v
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | `dev-secret-key` | Flask secret key |
| `JWT_SECRET_KEY` | `dev-jwt-secret` | JWT signing key |
| `DATABASE_URL` | `sqlite:///expense_tracker.db` | SQLAlchemy DB URI |
| `JWT_ACCESS_TOKEN_EXPIRES` | `900` | Access token TTL in seconds (15 min) |
| `JWT_REFRESH_TOKEN_EXPIRES` | `2592000` | Refresh token TTL (30 days) |

---

## API Overview

### Auth — `/api/auth`

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/register` | Register new user → returns tokens |
| POST | `/api/auth/login` | Login → returns tokens |
| POST | `/api/auth/refresh` | Exchange refresh token for new access token |
| POST | `/api/auth/logout` | Revoke current access token |

### Users — `/api/users`

| Method | Path | Description |
|---|---|---|
| GET | `/api/users/me` | Get own profile |
| PUT | `/api/users/me` | Update name / email |
| PUT | `/api/users/me/password` | Change password |

### Categories — `/api/categories`

| Method | Path | Description |
|---|---|---|
| GET | `/api/categories` | List all (default + own custom) |
| POST | `/api/categories` | Create custom category |
| PUT | `/api/categories/:id` | Update own custom category |
| DELETE | `/api/categories/:id` | Delete own custom category |

### Transactions — `/api/transactions`

| Method | Path | Description |
|---|---|---|
| GET | `/api/transactions` | List with filters, sort, pagination |
| POST | `/api/transactions` | Create |
| GET | `/api/transactions/:id` | Get by ID |
| PUT | `/api/transactions/:id` | Update |
| DELETE | `/api/transactions/:id` | Delete |

**Query params for GET /api/transactions:**

| Param | Type | Description |
|---|---|---|
| `type` | `expense` \| `income` | Filter by type |
| `category_id` | integer | Filter by category |
| `start_date` | YYYY-MM-DD | Date range start |
| `end_date` | YYYY-MM-DD | Date range end |
| `sort_by` | `date` \| `amount` | Sort field (default: `date`) |
| `order` | `asc` \| `desc` | Sort order (default: `desc`) |
| `page` | integer | Page number (default: 1) |
| `per_page` | integer | Items per page, max 100 (default: 20) |

### Analytics — `/api/analytics`

| Method | Path | Description |
|---|---|---|
| GET | `/api/analytics/summary` | Total income, expenses, net for a period |
| GET | `/api/analytics/breakdown` | Spending by category with percentages |
| GET | `/api/analytics/monthly` | Month-over-month summary |

---

## Authentication Flow

```
Register / Login → { access_token, refresh_token }
   ↓
Include header: Authorization: Bearer <access_token>
   ↓
Access token expires (15 min) → POST /api/auth/refresh with refresh_token
   ↓
Logout → POST /api/auth/logout (token added to blocklist, revoked immediately)
```

---

## Response Format

All endpoints return consistent JSON:

```json
// Success
{
  "success": true,
  "message": "...",
  "data": { ... },
  "meta": { "page": 1, "total": 42, ... }   // only on paginated endpoints
}

// Error
{
  "success": false,
  "message": "Validation failed",
  "errors": { "field": "reason" }
}
```

---

## Security Highlights

- Passwords hashed with bcrypt (never stored plain text)
- JWT access tokens expire in 15 minutes; refresh tokens in 30 days
- Revoked tokens stored in a DB blocklist — checked on every request
- Authorization enforced at data level — all queries are scoped to `user_id`
- Rate limiting on all auth endpoints (10 req/min)
- Stack traces never exposed to clients

---

## Deployment (Render / Railway)

1. Push repo to GitHub
2. Set environment variables (`SECRET_KEY`, `JWT_SECRET_KEY`, `DATABASE_URL`)
3. Set start command: `gunicorn run:app`
4. Swagger docs will be live at `<your-url>/docs`

> For production, switch `DATABASE_URL` to a PostgreSQL connection string — no code changes needed.

---

## Assumptions & Trade-offs

- **SQLite for local dev**: Swapping to Postgres requires only a `DATABASE_URL` change.
- **In-memory rate limiter**: Works per-process. For multi-worker prod deployments, configure `RATELIMIT_STORAGE_URI` to Redis.
- **No email verification**: Out of scope for this assignment.
- **Token blocklist uses DB**: Slightly slower than Redis but zero extra infra for local use.

## What I'd Improve With More Time

- Switch token blocklist to Redis for O(1) lookups at scale
- Add email verification flow
- Add soft-delete for transactions (audit trail)
- Add currency support per transaction
- Structured request/response logging with correlation IDs
- Docker + docker-compose for fully portable local setup
