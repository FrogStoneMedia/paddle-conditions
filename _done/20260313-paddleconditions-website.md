# TPP: PaddleConditions Landing Page Website

## Summary

Build paddleconditions.com as a static Astro 6 landing page. Showcases the Home Assistant integration with hero section, feature grid, screenshots, how-it-works flow, and coming-soon tease for web/mobile apps. Deploy to existing cPanel hosting.

## Current phase

- [x] Research & Planning
- [x] Design alternatives
- [x] Task breakdown
- [ ] Implementation
- [ ] Review & Refinement
- [ ] Final Integration
- [ ] Review

## Required reading

- `docs/images/` — 4 screenshots available (detail-overlay, tahoe-overlay, dashboard-mobile, forecast-cards)
- `../BestTreesToPlant/astro.config.mjs` — reference Astro config (static output, sitemap, tailwind vite)
- `../BestTreesToPlant/package.json` — reference dependency versions
- `../VanBriggle/astro.config.mjs` — reference for git-based lastmod, inline stylesheets

## Description

The project needs a public-facing website at paddleconditions.com. Phase 1 is a landing page that markets the HA integration. Phase 2 (future) adds a live web app with user accounts and data sync.

The site lives in `website/` inside the PaddleConditions monorepo, using Astro 6.x + Tailwind CSS 4 — matching the stack of Michael's other sites (VanBriggle, BestTreesToPlant). Static build uploads to cPanel shared hosting.

## Lore

- Both reference projects (VanBriggle, BestTreesToPlant) use Astro 5.x — this will be Astro 6.0.4
- Domain paddleconditions.com is already on Cloudflare DNS
- cPanel deploy: upload `dist/` contents to `public_html/paddleconditions.com/`
- No .htaccess needed — Astro generates proper HTML file structure
- Color palette reuses integration scoring colors for brand continuity: Go #4CAF50, Caution #FF9800, No-go #F44336
- Michael's writing style preference: cut fluff, keep excitement, one-line context for jargon
- Brand name is "Paddle Conditions" (two words) in all public-facing copy
- Backend API is live at https://api.paddleconditions.com/ — auth, billing, sync all working
- app.paddleconditions.com needs to be built (premium web app behind login wall)
- Cloudflare Turnstile needed on: registration, login, checkout/subscribe flows
- SSH to cPanel: `ssh -p 11208 -i ~/.ssh/paddleconditions devsac@104.255.174.113`
- cPanel Passenger Node.js apps: env vars set via Application Manager UI, need `rebuildhttpdconf && systemctl restart httpd` from root after config changes
- Passenger uses `app.js` as default startup file — we have a wrapper that imports `dist/index.js`
- Deploy workflow: `.github/workflows/deploy-api.yml` — rsync via self-hosted runner, excludes `.env.cron` and `tmp/`

## Solutions

### Option A (chosen): Astro 6 static site

Astro 6.x with Tailwind 4, sitemap, astro-seo, sharp. Static output mode. Matches existing project conventions exactly.

**Pros:** Known stack, cPanel-compatible, zero runtime cost, SEO-friendly.
**Cons:** No dynamic features (fine for landing page).

### Option B (rejected): Next.js or similar

Would require Node.js hosting, which cPanel doesn't support well.

## Tasks

### Chunk 1: Project Setup (Tasks 1-3)

- [ ] **Task 1: Initialize Astro project**
  - Create `website/package.json` with Astro 6.0.4, Tailwind 4, sitemap, seo, sharp
  - Create `website/astro.config.mjs` — static output, site: paddleconditions.com, tailwind vite plugin, sitemap
  - Create `website/tsconfig.json` — extend astro/tsconfigs/strict
  - Verify: `cd website && npm install && npm run build`

- [ ] **Task 2: Base layout and global styles**
  - Create `src/styles/global.css` — Tailwind imports + custom properties (scoring colors)
  - Create `src/layouts/BaseLayout.astro` — HTML shell, SEO head, global styles
  - Verify: build succeeds

- [ ] **Task 3: Header and Footer components**
  - Create `src/components/Header.astro` — responsive nav with mobile hamburger
  - Create `src/components/Footer.astro` — GitHub link, license, FrogStoneMedia attribution
  - Verify: build succeeds

### Chunk 2: Landing Page Sections (Tasks 4-8)

- [ ] **Task 4: Hero section**
  - Create `src/components/Hero.astro` — headline, subhead, CTA button, hero screenshot
  - Copy screenshots from `docs/images/` to `public/images/`
  - Verify: build succeeds, images included in dist/

- [ ] **Task 5: Feature cards**
  - Create `src/components/FeatureCard.astro` — icon + title + description card
  - Implement features grid section in index with 4-6 cards

- [ ] **Task 6: Screenshots gallery**
  - Create `src/components/ScreenshotGallery.astro` — responsive image grid
  - 4 screenshots: detail-overlay, tahoe-overlay, dashboard-mobile, forecast-cards

- [ ] **Task 7: How-it-works and data sources sections**
  - 3-step flow: Install via HACS, Add your spots, Check your dashboard
  - Data sources: Free APIs, no accounts, no keys

- [ ] **Task 8: Coming soon and problem statement sections**
  - Problem statement: "Stop checking four apps before every paddle"
  - Coming soon: tease web app and mobile app

### Chunk 3: Pages and Finalization (Tasks 9-11)

- [ ] **Task 9: Compose index.astro**
  - Assemble all sections into landing page
  - Verify: `npm run build && npm run preview`

- [ ] **Task 10: Additional pages**
  - Create `src/pages/404.astro` — simple 404
  - Create `src/pages/privacy.astro` — placeholder privacy page

- [ ] **Task 11: SEO and final build**
  - Create `src/components/SEO.astro` — meta tags, OG wrapper
  - Add `public/favicon.svg`
  - Final build and preview verification
  - Verify: `npm run build && npm run preview` serves correctly

## Design Direction

- Clean, modern, outdoor/water feel
- Color palette: Go green #4CAF50, Caution amber #FF9800, No-go red #F44336, water blue accent
- Dark header/footer, light content sections
- Mobile-first responsive

## Project Structure

```
website/
├── astro.config.mjs
├── package.json
├── tsconfig.json
├── public/
│   ├── favicon.svg
│   └── images/
├── src/
│   ├── styles/global.css
│   ├── layouts/BaseLayout.astro
│   ├── components/
│   │   ├── Header.astro
│   │   ├── Footer.astro
│   │   ├── Hero.astro
│   │   ├── FeatureCard.astro
│   │   ├── ScreenshotGallery.astro
│   │   └── SEO.astro
│   └── pages/
│       ├── index.astro
│       ├── 404.astro
│       └── privacy.astro
```
