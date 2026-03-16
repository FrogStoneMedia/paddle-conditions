# Backend API Implementation

## Goal
Build the Fastify backend API for PaddleConditions: auth, billing, sync, and scheduled jobs.

## Key Files
- **Spec:** `docs/superpowers/specs/2026-03-14-backend-api-stripe-auth-design.md`
- **Plan 1 (Auth):** `docs/superpowers/plans/2026-03-14-backend-api-auth.md`
- **Plan 2 (Billing):** `docs/superpowers/plans/2026-03-15-backend-api-billing.md`
- **Plan 3 (Sync):** `docs/superpowers/plans/2026-03-15-backend-api-sync.md`
- **Plan 4 (Jobs):** `docs/superpowers/plans/2026-03-16-backend-api-jobs.md`
- **API source:** `api/src/`
- **API tests:** `api/tests/`

## Phases

- [x] Phase 1: Design spec (reviewed, 12 issues fixed)
- [x] Phase 2: Plan 1 - Foundation + Auth (written, reviewed, all issues fixed)
- [x] Phase 3: Implement Plan 1 - Foundation + Auth (51 tests, 12 endpoints)
- [x] Phase 4: Write Plan 2 - Billing & Subscriptions
- [x] Phase 5: Implement Plan 2
- [x] Phase 6: Write Plan 3 - Data Sync
- [x] Phase 7: Implement Plan 3
- [x] Phase 8: Write Plan 4 - Scheduled Jobs
- [x] Phase 9: Implement Plan 4
- [x] Phase 10: Deployment setup (cPanel, GitHub Actions, Cloudflare routing)

## Tasks - Plan 1 (Complete)

- [x] Scaffold project (package.json, tsconfig, vitest, env files)
- [x] Config plugin + error classes
- [x] Database schema (all 6 tables) + Drizzle setup + migrations
- [x] Fastify server + health endpoint + test infrastructure
- [x] Auth service (createUser, verifyPassword, social linking)
- [x] Token service (JWT, refresh rotation, family tracking, reuse detection)
- [x] Auth plugin (JWT verification decorator)
- [x] Registration endpoint
- [x] Login endpoint
- [x] Refresh token endpoint
- [x] Email service (Resend wrapper)
- [x] Email verification endpoint
- [x] Password reset (forgot + reset)
- [x] Google OAuth endpoint
- [x] Apple Sign-In endpoint
- [x] Logout + sign-out-everywhere
- [x] Account deletion
- [x] Rate limiting (per-email on auth routes) + CORS
- [x] Integration test (full auth flow)

## Tasks - Plan 2 (Complete)

- [x] Write Plan 2: Billing & Subscriptions (`docs/superpowers/plans/2026-03-15-backend-api-billing.md`)
- [x] Stripe checkout + webhooks (5 events)
- [x] Apple IAP receipt validation + Server Notifications v2
- [x] Google Play Billing verification + RTDN
- [x] Subscription state machine (7 transitions incl. self-transition)
- [x] Multiple subscription prevention (row-level locking on users table)
- [x] Unified subscription status endpoint
- [x] Webhook idempotency (dedup table)
- [x] Account deletion billing integration (Stripe cancel + Apple/Google tombstones)
- [x] Integration test (full Stripe lifecycle, multi-sub prevention, idempotency)

## Lore

- **MariaDB via Homebrew:** `brew install mariadb && brew services start mariadb`. Connect as current macOS user (not root). Test DB: `paddle_conditions_test`, user: `paddle_test`, password: `test`.
- **Drizzle `mode: 'default'`:** The Task 1 implementer added `mode: 'default'` to the `drizzle()` call. Plan originally omitted it but it was needed for schema-aware queries.
- **DB type:** The project uses `Database = MySql2Database<typeof schema>` exported from `plugins/db.ts`, not the plan's generic `MySql2Database<Record<string, never>>`.
- **Token format:** Refresh tokens use `familyId.randomPart` format. The familyId is a UUIDv7 embedded in the token so reuse detection can look up the family even after the hash is rotated out of the sessions table.
- **Apple auth isolation:** Apple token verification is in its own `services/apple-auth.ts` module so tests can mock it without breaking `jose` (which TokenService also uses).
- **Rate limit in tests:** The test helper registers `@fastify/rate-limit` with max=1000 so normal tests aren't affected. The rate-limit test file creates its own app instance with real limits.
- **Google OAuth:** Spec was updated from "code flow" to "ID token flow" (Google's recommended mobile approach). Client sends ID token directly.
- **Cookies deferred:** httpOnly cookie refresh token delivery is deferred to the web app plan. Mobile apps use Keychain/Keystore.
- **Error handler:** Uses `instanceof AppError` check instead of duck-typing for cleaner TypeScript.
- **FOR UPDATE locking:** Lock the `users` row, not `subscriptions`, for multi-sub prevention. Empty result sets only get gap locks under REPEATABLE READ, which don't prevent concurrent INSERTs.
- **Stripe SDK types:** The latest Stripe SDK dropped `current_period_end` from the TypeScript `Subscription` type (though the API still returns it). Webhook event data objects are typed as `any` to work around this.
- **Self-transition:** The state machine allows `active -> active` to enable `currentPeriodEnd` updates from `customer.subscription.updated` webhooks on period renewals and plan changes.
- **Webhook encapsulation:** Stripe webhook route uses Fastify encapsulation in `stripe/index.ts` to override the JSON content type parser with a raw Buffer parser. The parser override is in the index, not in the webhook route itself.
- **Apple/Google services:** Mocked via app decoration (`app.appleIAP`, `app.googlePlay`). Production implementations are stubs that throw "not configured" until real API integration.
- **MySQL timestamp precision:** Test helpers truncate Date milliseconds to zero because MySQL TIMESTAMP columns have second precision. Without this, round-trip assertions fail on sub-second differences.

## Tasks - Plan 3 (Complete)

- [x] Write Plan 3: Data Sync (`docs/superpowers/plans/2026-03-15-backend-api-sync.md`)
- [x] Premium gate preHandler (403 for non-subscribers)
- [x] SyncService: cursor-based pull (UUIDv7 ordering) for locations + preferences
- [x] SyncService: last-write-wins push (server wins on tie) for locations + preferences
- [x] GET/POST /sync/locations routes with JSON schema validation (max 100 items)
- [x] GET/POST /sync/preferences routes with JSON schema validation (max 50 items)
- [x] UUID format validation on client-sent IDs
- [x] Integration test (full lifecycle, conflicts, soft deletes, premium gating)

## Lore (continued)

- **Fastify preHandler must return:** When sending a response in a preHandler (e.g., 403 in premium gate), you MUST `return reply.send(...)`. Without `return`, Fastify continues to the route handler and tries to send a second response, causing "Reply already sent" errors in production (masked in tests by `app.inject()`).
- **Push cursor ordering:** Push cursor must use the max UUIDv7 among accepted IDs (via `reduce`), not the last element of the accepted array. If items arrive out of order, last-element gives the wrong cursor.
- **Drizzle json columns:** Drizzle auto-serializes JSON columns. Do NOT wrap values in `JSON.stringify()` before passing to Drizzle, or you'll get double-encoded strings. MariaDB/mysql2 returns json values as raw strings on read.
- **N+1 in push:** pushLocations/pushPreferences do one SELECT + one INSERT/UPDATE per item. Acceptable for current payload limits (100/50) but should be batch-optimized if limits increase.
- **Preferences duplicate key:** If a client pushes two preferences with the same `key` but different IDs in one batch, the second insert hits the UNIQUE(user_id, key) constraint and throws an unhandled 500. Edge case, not yet fixed.

## Tasks - Plan 4 (Complete)

- [x] Write Plan 4: Scheduled Jobs (`docs/superpowers/plans/2026-03-16-backend-api-jobs.md`)
- [x] Job bootstrap module (shared DB connection lifecycle)
- [x] Schema migration (notification tracking columns on subscriptions)
- [x] Session cleanup job (expired sessions)
- [x] Webhook dedup cleanup job (events > 7 days)
- [x] Subscription expiry fallback job (canceled/past_due -> expired when past period)
- [x] Data retention purge job (locations/prefs for expired subs 30+ days, with re-subscribe guard)
- [x] Soft-delete + tombstone purge job (90-day soft-deletes + orphaned tombstones)
- [x] Expiration notification job (Day 0 + Day 23 emails with dedup + re-subscribe guard)
- [x] Integration test (full lifecycle, cleanup, dedup)

## Lore (continued 2)

- **buildApp afterEach closes pool:** The test helper `tests/helpers/app.ts` registers a global `afterEach` that closes the app (and its DB pool). Tests using `beforeAll` to set up the app fail on the second test because the pool is already closed. Always use `beforeEach` to rebuild the app per test.
- **Drizzle delete/update return type:** `db.delete().where()` and `db.update().set().where()` return `[ResultSetHeader, FieldPacket[]]`. Access `result[0].affectedRows` for the count. This is a mysql2 driver detail, not documented in Drizzle's own types.
- **isDirectRun guard for job scripts:** Use `process.argv[1]?.endsWith('job-name.js')` to detect direct CLI execution. During Vitest, `process.argv[1]` is the Vitest worker path, so the guard doesn't fire. This lets tests import the exported function without triggering `runJob()` (which calls `process.exit`).
- **Notification re-subscribe guard:** Before sending expiration emails, query for users with active/past_due/canceled subs. Skip those users even if they have an old expired record. Without this, re-subscribed users get "your subscription expired" emails.
- **drizzle-kit push broken:** `drizzle-kit push` fails with `TypeError: Cannot read properties of undefined (reading 'checkConstraint')` on this version. Use direct SQL via mysql CLI for schema changes: `mysql -u$DB_USER -p$DB_PASSWORD $DB_NAME -e "ALTER TABLE..."`.

## Session Notes -- 2026-03-16

### Completed
- Wrote Plan 3 (Data Sync) with 8 tasks across 3 chunks, plan reviewed (6 issues found and fixed)
- Implemented all 8 tasks via subagent-driven development
- Final review found 3 critical issues (premium gate return bug, UUID validation, cursor ordering) + 3 important issues - all critical fixed
- 184 tests passing (45 new), 12 new files (+2,009 lines), squash-merged to main as `832f9d7`
- Wrote Plan 4 (Scheduled Jobs) with 10 tasks across 4 chunks, plan reviewed (5 issues found and fixed across two review rounds)
- Implemented all 10 tasks: 6 standalone job scripts + bootstrap module + schema migration + integration test
- 210 tests passing (24 new), 14 new files

### Next Steps
- Phase 10: Deployment setup. Read spec section 6 for cPanel/GitHub Actions/Cloudflare routing details. Key decisions needed:
  - GitHub Actions workflow: `npm ci -> build -> test -> rsync to cPanel -> restart Node.js app` (self-hosted runner `paddleconditions-mac`)
  - cPanel cron entries for 6 job scripts (recommend staggering times, e.g., cleanup at 3am, notifications at 9am)
  - Cloudflare routing: `/api/*` proxied to cPanel/Apache, `/` serves Astro site
  - Apache `.htaccess` to restrict inbound to Cloudflare IPs only (critical for rate limit integrity)
  - Production `.env` setup in cPanel Node.js app config
  - Production migration: run `ALTER TABLE` SQL for the `notification_sent_day0`/`notification_sent_day23` columns
