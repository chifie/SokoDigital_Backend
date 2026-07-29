# SokoDigital API

A production-grade **e-commerce marketplace backend** built with **FastAPI**, **SQLAlchemy** (async), **PostgreSQL**, and **Redis**.

## 🚀 Quick Star

```bash
# Clone & setup
git clone <repo> && cd SokoDigital_Backend
cp .env.example .env

# Start all services
make docker-up

# Or run locally
make install-dev
make migrate
make seed
uvicorn app.main:app --reload
```

- **API:** http://localhost:8000
- **Docs:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

---

## 📡 API Endpoints

### 🔐 Authentication (`/api/v1/auth`)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/register` | - | Register new user |
| POST | `/login` | - | Login (email or username) |
| GET | `/me` | ✅ | Get current user profile |
| PUT | `/me` | ✅ | Update profile |
| PUT | `/change-password` | ✅ | Change password |
| POST | `/verify-email` | - | Verify email with token |
| POST | `/resend-verification` | - | Resend verification email |
| POST | `/forgot-password` | - | Request password reset |
| POST | `/reset-password` | - | Reset password with token |

### 📦 Products (`/api/v1/products`)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/products` | - | List/search/filter/sort products |
| GET | `/products/featured` | - | Featured products |
| GET | `/products/trending` | - | Trending products |
| GET | `/products/{slug}` | - | Get product by slug |
| POST | `/products` | ✅ Seller | Create product |
| PUT | `/products/{id}` | ✅ Seller | Update product |
| DELETE | `/products/{id}` | ✅ Seller | Delete product |

**Search:** Full-text via PostgreSQL `tsvector` or **Meilisearch** (when `MEILISEARCH_URL` is configured).

### 📂 Categories (`/api/v1/categories`)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/categories` | - | List all categories |
| GET | `/categories/tree` | - | Category tree (for menus) |
| GET | `/categories/{slug}` | - | Get category by slug |
| POST | `/categories` | ✅ Admin | Create category |
| PUT | `/categories/{id}` | ✅ Admin | Update category |
| POST | `/categories/seed` | ✅ Admin | Seed 15 default categories |
| DELETE | `/categories/{id}` | ✅ Admin | Delete category |

### 🏪 Sellers (`/api/v1/sellers`)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/sellers/onboard` | ✅ | Register as seller |
| GET | `/sellers/me` | ✅ | Get my seller profile |
| PUT | `/sellers/me` | ✅ | Update seller profile |
| GET | `/sellers/dashboard` | ✅ | Seller dashboard stats |
| GET | `/sellers/{store_slug}` | - | Public seller profile |
| POST | `/sellers/{id}/follow` | ✅ | Toggle follow/unfollow |
| GET | `/sellers/{id}/followers` | - | List followers |
| GET | `/sellers/{id}/follow/status` | ✅ | Check follow status |
| GET | `/sellers/following/mine` | ✅ | My followed sellers |

### 🛒 Orders (`/api/v1/orders`)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/orders/checkout` | ✅ | Create order from cart |
| GET | `/orders` | ✅ | List my orders (paginated) |
| GET | `/orders/{id}` | ✅ | Get order details |
| PUT | `/orders/{id}/status` | ✅ Seller | Update order status |

### 📍 Addresses (`/api/v1/addresses`)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/addresses` | ✅ | List my addresses |
| POST | `/addresses` | ✅ | Create address |
| GET | `/addresses/{id}` | ✅ | Get address |
| PUT | `/addresses/{id}` | ✅ | Update address |
| DELETE | `/addresses/{id}` | ✅ | Delete address |

### ⭐ Reviews (`/api/v1/reviews`)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/reviews/mine` | ✅ | My reviews |
| GET | `/reviews/product/{id}` | - | Product reviews |
| POST | `/reviews` | ✅ | Create review |
| PUT | `/reviews/{id}` | ✅ | Update review |
| DELETE | `/reviews/{id}` | ✅ | Delete review |

### ❤️ Wishlist (`/api/v1/wishlist`)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/wishlist` | ✅ | List wishlist |
| POST | `/wishlist` | ✅ | Add to wishlist |
| DELETE | `/wishlist/{product_id}` | ✅ | Remove from wishlist |

### 💬 Messaging (`/api/v1/conversations`)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/conversations` | ✅ | List conversations |
| POST | `/conversations` | ✅ | Start conversation |
| GET | `/conversations/unread/count` | ✅ | Unread message count |
| GET | `/conversations/{id}` | ✅ | Conversation detail |
| POST | `/conversations/{id}/messages` | ✅ | Send message |
| GET | `/conversations/{id}/messages` | ✅ | Get messages (polling) |

### 🎯 Engagement
**Coupons** (`/api/v1/coupons`)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/coupons/validate` | - | Validate coupon code |
| GET | `/coupons` | ✅ Admin | List coupons |
| POST | `/coupons` | ✅ Admin | Create coupon |
| PUT | `/coupons/{id}` | ✅ Admin | Update coupon |
| DELETE | `/coupons/{id}` | ✅ Admin | Delete coupon |

**Flash Sales** (`/api/v1/flash-sales`), **Banners** (`/api/v1/banners`), **Notifications** (`/api/v1/notifications`) — Full CRUD with admin auth.

### 🤖 AI & Extras (`/api/v1/*`)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/ai/chat` | Optional | AI shopping assistant |
| POST | `/newsletter/subscribe` | - | Subscribe to newsletter |
| POST | `/newsletter/unsubscribe` | - | Unsubscribe |
| GET | `/newsletter/subscribers` | ✅ Admin | List subscribers |

### 🔗 Webhooks (`/api/v1/webhooks`)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/webhooks` | ✅ | List my webhooks |
| POST | `/webhooks` | ✅ | Register webhook |
| GET | `/webhooks/{id}` | ✅ | Get webhook |
| PUT | `/webhooks/{id}` | ✅ | Update webhook |
| DELETE | `/webhooks/{id}` | ✅ | Delete webhook |
| POST | `/webhooks/{id}/test` | ✅ | Send test ping |
| GET | `/webhooks/{id}/deliveries` | ✅ | Delivery history |

### 📁 Uploads (`/api/v1/uploads`)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/uploads/image` | ✅ | Upload image |
| POST | `/uploads/document` | ✅ | Upload document |
| POST | `/uploads/any` | ✅ | Upload any file |

### 🛡️ Admin (`/api/v1/admin`)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/admin/users` | ✅ Admin | List users |
| GET | `/admin/users/{id}` | ✅ Admin | Get user details |
| PUT | `/admin/users/{id}/role` | ✅ Admin | Update role |
| PUT | `/admin/users/{id}/toggle-active` | ✅ Admin | Toggle active |
| GET | `/admin/products` | ✅ Admin | List products |
| PUT | `/admin/products/{id}/status` | ✅ Admin | Moderate product |
| GET | `/admin/dashboard` | ✅ Admin | Dashboard stats |
| GET | `/admin/analytics/revenue` | ✅ Admin | Revenue analytics |
| GET | `/admin/analytics/top-products` | ✅ Admin | Top products |
| GET | `/admin/analytics/by-category` | ✅ Admin | Revenue by category |

---

## 🛡️ Security

- **JWT auth** with configurable expiry (default 8h)
- **Passwords** hashed with bcrypt
- **Rate limiting** — 10/min auth, 20/min upload, 100/min general (in-memory or Redis)
- **CORS** configured for frontend origins
- **Sentry** error tracking (optional)
- **Webhook** payloads signed with HMAC-SHA256
- **Sensitive data** scrubbed from error reports

---

## 🧪 Testing

```bash
# Unit tests (no database required)
make test                          # 56 tests

# All tests (requires PostgreSQL)
make test-all                      # 141 tests

# Docker-based E2E (isolated, ephemeral)
make test-e2e

# Coverage report
python -m pytest tests/ --cov=app --cov-report=html
```

---

## 🐳 Docker

```bash
# Development
docker compose up -d --build       # Starts db, redis, api, worker

# Production-like E2E tests
docker compose -f docker-compose.test.yml up --build --abort-on-container-exit
```

**Services:**
| Service | Image | Port |
|---------|-------|------|
| `api` | Custom (Dockerfile) | 8000 |
| `db` | postgres:16-alpine | 5432 |
| `redis` | redis:7-alpine | 6379 |
| `worker` | Custom (ARQ) | - |

---

## 🔧 Configuration (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection |
| `SECRET_KEY` | `change-me-in-production` | JWT signing key |
| `REDIS_URL` | - | Redis for rate limiting & caching |
| `SENTRY_DSN` | - | Error tracking |
| `MEILISEARCH_URL` | - | Full-text search engine |
| `SMTP_HOST` | - | Email sending |
| `AI_API_KEY` | - | OpenAI-compatible API key |

---

## 📊 Stack

- **Framework:** FastAPI 0.115
- **Database:** PostgreSQL 16 + SQLAlchemy 2.0 (async)
- **Cache:** Redis 7
- **Migration:** Alembic 1.14
- **Auth:** JWT (python-jose) + bcrypt (passlib)
- **Background:** ARQ (Redis-based task queue)
- **Monitoring:** Prometheus metrics, OpenTelemetry tracing, Sentry
- **Search:** PostgreSQL `tsvector` + Meilisearch (optional)
- **Email:** SMTP with HTML templates
- **CI:** GitHub Actions (lint, test, build, coverage)
