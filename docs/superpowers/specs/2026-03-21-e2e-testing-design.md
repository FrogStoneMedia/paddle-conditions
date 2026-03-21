# E2E Testing Design Spec

## Overview

Add end-to-end tests to the Paddle Conditions web app (React SPA) using Playwright. The tests serve as a regression safety net and provide confidence for refactoring. They run locally against a local API instance with a test database.

## Goals

- Cover the four critical user flows: auth, subscription, location management, account management
- Run against local dev API (not production) for isolation and repeatability
- Mock Stripe redirects via network interception (no real Stripe dependency)
- Use Cloudflare Turnstile always-pass test keys (no CAPTCHA friction)
- Clean up test data after each suite (no state leakage)

## Non-Goals

- CI integration (future work)
- Cross-browser testing (Chromium only for now)
- Visual regression testing
- Performance testing

## Important: No Hardcoded Secrets in Production Code

The app currently hardcodes `API_BASE` and `TURNSTILE_SITE_KEY` in multiple files. As part of this work, we will centralize these into environment-configurable constants. This is a broader principle: production code should never contain hardcoded API URLs, keys, or credentials. All such values must come from environment variables with sensible defaults.

## Architecture

### Project Structure

```
app/
  e2e/
    fixtures/
      auth.ts            # Shared auth fixture (register, login, subscribe, cleanup)
    tests/
      auth.spec.ts       # Register, login, logout, token refresh
      subscription.spec.ts  # Subscribe flow with mocked Stripe
      locations.spec.ts  # Search, configure, add, view detail
      account.spec.ts    # Password, theme, subscription mgmt, delete
    playwright.config.ts
  .env.test              # VITE_API_BASE=http://localhost:3000, VITE_TURNSTILE_SITE_KEY=1x00000000000000000000AA
```

### Environment Configuration

**App changes (production code improvement):**
- `app/src/lib/api.ts`: Export `API_BASE` as `import.meta.env.VITE_API_BASE || 'https://api.paddleconditions.com'`
- `app/src/lib/api.ts`: Export `TURNSTILE_SITE_KEY` as `import.meta.env.VITE_TURNSTILE_SITE_KEY || '0x4AAAAAACsMxuk7cAUe95vr'`
- All pages that redeclare `API_BASE` must import from `api.ts` instead:
  - `LoginPage.tsx` - has its own `API_BASE` and `TURNSTILE_SITE_KEY`
  - `RegisterPage.tsx` - has its own `API_BASE` and `TURNSTILE_SITE_KEY`
  - `ForgotPasswordPage.tsx` - has its own `API_BASE` and `TURNSTILE_SITE_KEY`
  - `AddLocationPage.tsx` - has its own `API_BASE` (uses raw `fetch`, not `apiFetch`)
  - `theme.tsx` - has its own `API_BASE` (uses raw `fetch` for `/sync/preferences`)
- Pages using raw `fetch()` with `API_BASE` (theme.tsx, AddLocationPage.tsx) must be migrated to use the centralized import. Consider converting them to use `apiFetch` for consistency.

**Test environment:**
- App `.env.test`: Points `VITE_API_BASE` at `http://localhost:3000`
- App `.env.test`: Sets `VITE_TURNSTILE_SITE_KEY` to Cloudflare's always-pass test key `1x00000000000000000000AA`
- API test env: No `TURNSTILE_SECRET_KEY` set (disables server-side verification)
- API test env: Uses existing `paddle_conditions_test` database

### Turnstile Strategy

The API already supports disabling Turnstile: `turnstile.enabled` is `false` when `TURNSTILE_SECRET_KEY` is unset (see `api/src/plugins/config.ts:50-51`). Combined with Cloudflare's always-pass test site key on the frontend, the CAPTCHA widget renders and returns a token that the API accepts without verifying. No mocking needed.

### Stripe Mock Strategy

**Important:** The API's `/stripe/webhook` endpoint verifies signatures via `stripe.webhooks.constructEvent()`. Raw POST calls without a valid signature will get 400. Two approaches to handle this:

**Option A: Test seed endpoint (recommended).** Add a `POST /test/seed-subscription` endpoint on the API that only exists when `NODE_ENV=test`. This endpoint directly inserts a subscription record via `BillingService`, bypassing Stripe entirely. Simple, no crypto needed.

**Option B: Signed webhook simulation.** Set `STRIPE_WEBHOOK_SECRET` in the test API env and use `stripe.webhooks.generateTestHeaderString()` in the test fixture to construct a properly signed payload. More realistic but adds Stripe SDK as a test dependency.

**UI subscription flow (subscription.spec.ts):**
- Intercept the redirect to `checkout.stripe.com` via `page.route()` after clicking Subscribe
- Seed the subscription via the test seed endpoint (Option A)
- Verify the app's post-checkout polling detects the active subscription

**Auth fixture (other suites):** Seed subscription via the test seed endpoint after user registration. No Stripe interaction needed.

### Auth Fixture

Shared Playwright fixture that provides a logged-in, subscribed user:

1. **Setup:** Register a unique user (timestamped email) via direct API call to `/auth/register`
2. **Subscribe:** Seed subscription via test seed endpoint (`POST /test/seed-subscription`)
3. **Auth state:** Inject `refreshToken` into browser localStorage via `page.evaluate(() => localStorage.setItem('refreshToken', token))`. The app's silent refresh on mount will exchange it for an accessToken automatically.
4. **Teardown:** Delete the test user via API to clean up

**Note on localStorage injection:** Playwright fixtures run in Node.js, not the browser. Token injection must use `page.evaluate()` or Playwright's `storageState` mechanism, not direct `localStorage` calls.

Each test file gets a fresh user. No shared state between suites. The login UI flow is tested explicitly in `auth.spec.ts`; other suites skip it by seeding tokens directly.

## Test Suites

### auth.spec.ts (5 tests)

1. **Register new account** - Fill email/password/confirm form, submit, verify redirect to /dashboard (note: redirect goes to /subscribe only when `?plan=` query param is present; default is /dashboard)
2. **Login with valid credentials** - Seed subscription for test user first, then fill email/password, submit, verify redirect to /dashboard
3. **Login with wrong password** - Submit bad password, verify error message displayed
4. **Logout** - Click sign out on account page, verify redirect to /
5. **Token refresh** - Login, clear in-memory accessToken (simulate expiry), navigate, verify still authenticated via refresh

### subscription.spec.ts (3 tests)

1. **Subscribe page shows plans** - Verify monthly ($3.99) and yearly ($34) options visible
2. **Subscribe flow** - Click monthly, intercept Stripe redirect, simulate webhook, verify redirect to /dashboard
3. **Unsubscribed user redirect** - Navigate to /dashboard without subscription, verify redirect to /subscribe

### locations.spec.ts (5 tests, uses auth fixture)

1. **Empty dashboard CTA** - Fresh user sees "Add Your First Location" prompt
2. **Search for location** - Type in search input, verify results appear after debounce (300ms)
3. **Full add flow** - Search -> select result -> configure name/activity/stations -> save -> verify card appears on dashboard
4. **View location detail** - Click location card -> verify detail page loads with conditions data and charts
5. **Dashboard condition cards** - After adding location, verify cards show scores and rating badges

### account.spec.ts (4 tests, uses auth fixture)

1. **Change password** - Fill current/new/confirm, submit, verify success toast
2. **Theme toggle** - Switch to dark mode, verify CSS variable changes, reload and verify persistence
3. **Manage subscription** - Click manage billing, intercept Stripe portal redirect, verify URL
4. **Delete account** - Type "DELETE", confirm, verify redirect to / and login fails

**Total: 17 tests**

## Playwright Configuration

```typescript
// playwright.config.ts key settings
{
  testDir: './e2e/tests',
  timeout: 30_000,
  retries: 0,
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: [
    {
      command: 'npm run dev -- --mode test',  // Vite dev server in test mode (loads .env.test)
      port: 5173,
      reuseExistingServer: true,
    },
    {
      command: 'npm run dev',                 // API server
      port: 3000,
      cwd: '../api',
      reuseExistingServer: true,
      env: {
        NODE_ENV: 'test',
        DB_HOST: 'localhost',
        DB_PORT: '3306',
        DB_USER: 'paddle_test',
        DB_PASSWORD: 'test',
        DB_NAME: 'paddle_conditions_test',
        JWT_SECRET: 'test-jwt-secret-do-not-use-in-production',
        STRIPE_SECRET_KEY: 'sk_test_fake',
        STRIPE_WEBHOOK_SECRET: 'whsec_test_fake',
        // TURNSTILE_SECRET_KEY intentionally omitted to disable verification
      },
    },
  ],
}
```

**Package.json scripts:**
- `test:e2e` - Run all tests headless
- `test:e2e:ui` - Playwright UI mode for debugging
- `test:e2e:headed` - Run with visible browser

## Dependencies

- `@playwright/test` (devDependency in app/)
- No other new dependencies

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Test DB state leaks between runs | Each suite creates fresh user, teardown deletes it |
| Turnstile widget slow to load | Always-pass test key returns immediately |
| API server not running | Playwright webServer config auto-starts it |
| Flaky async waits | Use Playwright's auto-wait and `waitForResponse` for API calls |
| Stripe webhook simulation timing | Use `waitForResponse` on subscription status endpoint after webhook call |
