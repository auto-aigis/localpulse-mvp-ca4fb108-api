# LocalPulse API Specification

## Base URL
`/api`

---

## Authentication Endpoints

### POST /api/auth/register
- **Request**: `{ email: EmailStr, password: str, display_name?: string }`
- **Response 200**: `{ status: "verification_sent", email: string }`
- **Auth**: none
- **Errors**: 400 (Email already registered)

### POST /api/auth/login
- **Request**: `{ email: EmailStr, password: str }`
- **Response 200**: `{ id: string, email: string, display_name?: string, is_email_verified: boolean, created_at: datetime }`
- **Auth**: none
- **Errors**: 401 (Invalid credentials), 403 (email_not_verified)
- **Cookie**: Sets `session_id` HTTP-only cookie

### POST /api/auth/logout
- **Request**: No body
- **Response 200**: `{ status: "logged_out" }`
- **Auth**: required
- **Cookie**: Clears `session_id` cookie

### GET /api/auth/me
- **Request**: No body
- **Response 200**: `{ id: string, email: string, display_name?: string, is_email_verified: boolean, created_at: datetime }`
- **Auth**: required
- **Errors**: 401 (Not authenticated)

### GET /api/auth/subscription
- **Request**: No body
- **Response 200**: `{ id: string, tier: string, status: string, billing_interval?: string, current_period_end?: datetime }`
- **Auth**: required

### POST /api/auth/verify-email
- **Request**: `{ token: string }`
- **Response 200**: `{ status: "verified" }`
- **Auth**: none
- **Errors**: 400 (Invalid or expired token), 404 (User not found)
- **Cookie**: Sets session cookie on success

### POST /api/auth/resend-verification
- **Request**: `{ email: EmailStr }`
- **Response 200**: `{ status: "sent" }`
- **Auth**: none

---

## Quiz Endpoints

### GET /api/quiz
- **Request**: No body
- **Response 200**: `{ id: string, user_id: string, event_types: string[], social_comfort?: string, budget_range?: string, schedule_prefs: string[], neighborhood: string, vibe_description?: string, updated_at: datetime }`
- **Auth**: required
- **Errors**: 404 (Taste profile not found)

### POST /api/quiz
- **Request**: `{ event_types?: string[], social_comfort?: string, budget_range?: string, schedule_prefs?: string[], neighborhood?: string, vibe_description?: string }`
- **Response 200**: TasteProfileResponse
- **Auth**: required
- **Creates or updates taste profile**

---

## Digest Endpoints

### GET /api/digest/current
- **Request**: No body
- **Response 200**: `{ digest?: { id: string, user_id: string, generated_at: datetime, events: EventWithVibeResponse[], tier_snapshot?: string, is_email_sent: boolean }, subscription_tier: string, can_upgrade: boolean }`
- **Auth**: required
- **Limits events by tier**: free=3, explorer=10, local=15

### GET /api/digest/history
- **Request**: No body
- **Response 200**: Array of past digests
- **Auth**: required
- **Errors**: 403 (Digest history requires Explorer tier or higher)

### POST /api/digest/generate
- **Request**: No body
- **Response 200**: `{ id: string, user_id: string, generated_at: datetime, events: EventWithVibeResponse[], tier_snapshot: string, is_email_sent: boolean }`
- **Auth**: required
- **Errors**: 400 (Please complete the taste quiz first), 500 (Failed to generate digest)
- **Generates AI-curated digest based on taste profile and feedback**

---

## Event Endpoints

### GET /api/events
- **Request**: Query params: `limit?: number`, `category?: string`
- **Response 200**: Array of events with fields: id, title, description, event_date, location, category, source_url, source_name, vibe_tags
- **Auth**: required

### POST /api/events/aggregate
- **Request**: No body
- **Response 200**: `{ status: "completed", total_events: number }`
- **Auth**: required
- **Fetches from Eventbrite and Reddit, deduplicates, stores in DB**

---

## Feedback Endpoints

### POST /api/feedback
- **Request**: `{ event_id: string, digest_id?: string, rating: string (thumbs_up|thumbs_down|1-5), source?: string }`
- **Response 200**: `{ id: string, user_id: string, event_id: string, rating: string, source: string, created_at: datetime }`
- **Auth**: required
- **Errors**: 403 (Feedback requires Explorer tier or higher)

---

## Settings Endpoints

### GET /api/settings/keys
- **Request**: No body
- **Response 200**: Array of `{ id: string, service_name: string, masked_key: string, created_at: datetime }`
- **Auth**: required

### PUT /api/settings/keys/{service_name}
- **Request**: `{ service_name: string, api_key: string }`
- **Response 200**: `{ status: "saved", service: string }`
- **Auth**: required
- **Errors**: 400 (Service name mismatch)

### DELETE /api/settings/keys/{service_name}
- **Request**: No body
- **Response 200**: `{ status: "deleted" }`
- **Auth**: required

### PUT /api/settings/alerts
- **Request**: `{ opted_in: boolean }`
- **Response 200**: `{ status: "updated", opted_in: boolean }`
- **Auth**: required
- **Errors**: 403 (Real-time alerts require Local tier)

---

## Payment Endpoints (Paddle)

### POST /api/payments/checkout
- **Request**: `{ tier: string (explorer|local), billing_interval: string (monthly|yearly) }`
- **Response 200**: `{ price_id: string, client_token: string }`
- **Auth**: required
- **Errors**: 400 (Invalid tier or pricing not configured)

### GET /api/subscription/manage
- **Request**: No body
- **Response 200**: `{ url: string }`
- **Auth**: required
- **Errors**: 400 (No active subscription)

### POST /api/paddle/webhook
- **Request**: Raw Paddle webhook payload
- **Response 200**: `{ status: "received" }`
- **Auth**: none (uses signature verification)
- **Errors**: 400 (Invalid signature format/JSON), 401 (Invalid signature), 500 (Webhook secret not configured)
- **Handles**: subscription.created, subscription.activated, subscription.updated, subscription.canceled, transaction.completed

### POST /api/payments/verify-transaction
- **Request**: `{ transaction_id: string }`
- **Response 200**: `{ status: string, tier?: string }`
- **Auth**: required
- **Errors**: 400 (Failed to verify/Transaction not completed), 500 (Paddle not configured)

---

## Health Check

### GET /health
- **Request**: No body
- **Response 200**: `{ status: "ok" }`
- **Auth**: none

---

## Subscription Tiers

| Tier | Max Events | Email Digest | Feedback | History | Real-time Alerts |
|------|------------|--------------|----------|---------|-------------------|
| Free | 3 | No | No | No | No |
| Explorer | 10 | Yes | Yes | Yes | No |
| Local | 15 | Yes | Yes | Yes | Yes |

---

## Paddle Price IDs (set via environment variables)
- `PADDLE_PRICE_ID_EXPLORER_MONTHLY` - Explorer monthly ($9/mo)
- `PADDLE_PRICE_ID_EXPLORER_YEARLY` - Explorer annual ($96/yr)
- `PADDLE_PRICE_ID_LOCAL_MONTHLY` - Local monthly ($19/mo)
- `PADDLE_PRICE_ID_LOCAL_YEARLY` - Local annual ($192/yr)