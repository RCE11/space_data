# Space Data Intelligence Platform — MVP Build Plan

**Ray | March 2026**

---

## Overview

This document breaks the MVP build (Weeks 5–8 of the 90-Day Validation Sprint) into four sequential phases. Each phase has a clear completion gate. Do not advance to the next phase until the current gate is met.

---

## Phase A: Data Foundation

Everything else depends on this. Get data flowing into a clean, normalized schema before touching the API.

### Work

- Design a PostgreSQL schema with core tables: `launches`, `satellites`, `operators`, `orbits`
- Build ingestion scripts for 2–3 primary sources:
  - Space-Track TLEs
  - UCS Satellite Database
  - FAA launch licenses
- Normalize and deduplicate across sources
- Schedule daily automated refresh (cron or simple task scheduler)

### Gate

You can query your own database and get accurate answers to: "What is launching in the next 90 days, and who operates those satellites?"

---

## Phase B: API Layer

Thin layer on top of the data. No business logic in the API — it reads from the database and returns JSON.

### Work

- FastAPI app with 4 endpoints:
  - `GET /launches/upcoming`
  - `GET /launches/history`
  - `GET /satellites/by-operator`
  - `GET /satellites/by-orbit`
- API key authentication (simple key table, nothing fancy)
- Basic rate limiting
- OpenAPI/Swagger docs auto-generated from FastAPI
- Deploy on Railway or Fly.io

### Gate

Someone with an API key can hit your endpoints and get back clean, accurate JSON.

---

## Phase C: Enrichment Layer

This is the manual curation moat. Raw data from public sources is noisy — your value is making it usable.

### Work

- Operator mapping: match satellites to companies, resolve name variations
- Orbit classification: LEO / MEO / GEO / SSO, standardized
- Constellation grouping: Starlink, OneWeb, Kuiper, etc.
- Internal admin workflow for flagging and correcting data issues quickly

### Gate

A non-technical user (investor, analyst) can look at your API output and immediately understand it without cross-referencing other sources.

---

## Phase D: Product Packaging

Make it real enough that someone can sign up, try it, and pay you — with zero manual intervention.

### Work

- Landing page with value prop, example queries, and signup form
- API key self-service provisioning
- Usage tracking (who is calling what, how often)
- Stripe integration for payment at two tiers:
  - Individual: $99–299/mo
  - Team / Enterprise: $500–1,000/mo
- Basic email onboarding (welcome + getting started)

### Gate

A stranger can find your site, sign up, get a key, make API calls, and pay you — end to end, unassisted.

---

## Phase Sequencing Rationale

| Order | Reason |
|---|---|
| A before B | No point building endpoints that return garbage data. Get the data right first. |
| B before C | A working API with rough data lets you demo to prospects while you enrich. Don't block outreach on perfect data. |
| C before D | Enrichment is what makes the free trial sticky. Curated, mapped, classified data is the value — not raw TLEs. |
| D last | Payment and self-service matter, but not until you have trial users ready to convert. |

---

## Technical Defaults

These are starting choices optimized for speed. Revisit only if a specific constraint forces it.

| Decision | Choice | Why |
|---|---|---|
| Language | Python | Best library support for space data (sgp4, astropy, spacetrack) |
| Framework | FastAPI | Auto-generates OpenAPI docs, async-ready, minimal boilerplate |
| Database | PostgreSQL | Structured relational data, strong query performance, free tier on Supabase |
| Hosting | Railway or Fly.io | Simple deploys, cheap, good enough for early traffic |
| Payments | Stripe | Industry standard, fast to integrate |
