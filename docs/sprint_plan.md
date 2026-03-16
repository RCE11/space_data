# Space Data Intelligence Platform

## 90-Day Validation Sprint

**Ray | March 2026**

---

## Objective

Validate whether space industry professionals will pay for clean, queryable access to launch manifest and satellite registry data. The sprint is designed to produce a clear go/no-go decision by Day 90, with minimal capital at risk.

---

## Starting Product Hypothesis

**Core question the product answers:** "Who is launching what satellites, when, and to what orbit?"

This is the narrowest valuable dataset in the space intelligence stack. It touches every buyer persona (investors, operators, insurers, analysts) and can be assembled from publicly available sources you already know how to navigate.

### Initial Data Scope

| Data Layer | Sources |
|---|---|
| Launch manifests | Space-Track, operator press releases, FAA/AST filings |
| Satellite registry | UCS Satellite Database, ITU filings, FCC IBFS |
| Orbital parameters | Space-Track TLEs, CelesTrak, owner/operator mapping |
| Operator profiles | SEC filings, Crunchbase, manual enrichment |

---

## Phase 1: Discovery & Demand Validation (Weeks 1–4)

**Goal:** Confirm that real buyers exist and will pay for this data. No code yet. This phase is entirely about conversations and a lightweight proof of concept.

| Week | Action | Deliverable / Gate |
|---|---|---|
| **1–2** | Identify 15–20 target buyers across 4 segments: NewSpace investors (VCs, PE funds), satellite operators, insurance underwriters, space consultants/analysts | Contact list of 20 names with roles and companies |
| **1–2** | Draft a one-page product concept with 3–4 example API endpoints and sample JSON responses | Product concept PDF to use in outreach |
| **2–3** | Conduct 8–10 discovery calls. Key questions: What data do you manually assemble today? How much time does it take? What would you pay to automate it? What's missing from existing tools? | Interview notes with pain points ranked by frequency |
| **3–4** | Build a static demo: hand-curated dataset of 50–100 upcoming launches with satellite details, served via a simple REST endpoint or static JSON | Working demo URL you can share in follow-up calls |
| **4** | Synthesize findings. Do at least 5 of 10 interviewees express willingness to pay? If not, pivot the data scope or target buyer before proceeding | GO / NO-GO decision document |

> **Key principle:** Use your Airbus network as the starting point. You have direct access to satellite operators and defense-adjacent contacts who can give you honest signal on willingness to pay.

---

## Phase 2: MVP Build (Weeks 5–8)

**Goal:** Ship a functional API with real, continuously updated data. Keep the stack simple. You are optimizing for speed to first paying user, not architectural elegance.

| Week | Action | Deliverable / Gate |
|---|---|---|
| **5–6** | Build data ingestion pipelines for 2–3 primary sources (Space-Track TLEs, UCS Satellite DB, FAA launch licenses). Automate daily refresh | Automated pipeline running on schedule |
| **5–6** | Design API schema: /launches/upcoming, /launches/history, /satellites/by-operator, /satellites/by-orbit. Keep it RESTful and dead simple | API spec document (OpenAPI/Swagger) |
| **6–7** | Build the API layer (Python/FastAPI or Node/Express), deploy on Railway or Fly.io. Add API key authentication and basic rate limiting | Live API with documentation page |
| **7–8** | Enrich data with manual curation: operator mapping, orbit classification, constellation grouping. This human layer is your moat in the early days | Enriched dataset covering 500+ active satellites and 50+ upcoming launches |
| **8** | Create a lightweight landing page with API docs, example queries, and a signup form for API keys | Public-facing product page |

> **Technical note:** Resist the urge to build a full frontend dashboard. The API is the product. A dashboard can come later once you understand what views buyers actually want.

---

## Phase 3: Early Revenue & Signal (Weeks 9–12)

**Goal:** Get 3–5 paying users or committed LOIs. Revenue at this stage validates the business, not the bank account.

| Week | Action | Deliverable / Gate |
|---|---|---|
| **9–10** | Go back to every discovery call contact with the live product. Offer a 30-day free trial with a clear price after ($99–299/mo for individual, $500–1,000/mo for team/enterprise) | Trial signups tracked |
| **9–10** | Cold outreach to 20–30 additional prospects using the product as a demo. Target NewSpace investors and consultants first — they have the fastest buying cycles | Outreach tracker with response rates |
| **10–11** | Iterate on data quality and coverage based on user feedback. Add the most-requested missing fields or endpoints | Changelog of improvements driven by user requests |
| **11–12** | Convert trial users to paid. Track: conversion rate, usage patterns, feature requests, willingness to pay at stated price points | Revenue dashboard and user metrics |
| **12** | Final assessment: Do you have 3+ paying users or strong LOIs? Is the feedback loop producing clear expansion opportunities? | 90-day retrospective and decision on next phase |

---

## Go / No-Go Decision Framework

At the end of 90 days, evaluate against these criteria to decide whether to invest further.

| Signal | 🟢 Green (Go) | 🟡 Yellow (Iterate) | 🔴 Red (Stop) |
|---|---|---|---|
| **Paying users** | 3+ paying or LOI | 1–2 paying, strong interest | 0 paying, weak interest |
| **Discovery calls** | 5+ said "I'd pay for this" | 3–4 interested but hedging | < 3 interested |
| **Usage pattern** | Weekly+ API calls from trials | Occasional usage, unclear habit | Signed up but never used |
| **Expansion signal** | Users ask for more data layers | Satisfied but no pull for more | No engagement after trial |

---

## Estimated Budget (90 Days)

This sprint is designed to be capital-light. The only real costs are infrastructure and your time.

| Item | Estimated Cost |
|---|---|
| Cloud hosting (Railway/Fly.io) | $20–50/mo |
| Domain + landing page | $15–30 |
| Database (Supabase/PlanetScale free tier) | $0–25/mo |
| Space-Track account | Free (requires registration) |
| **Total for 90 days** | **~$150–350** |

---

## Post-Sprint Expansion Roadmap

If the sprint produces a green-light decision, these are the natural next layers to add, in priority order. Each layer increases switching costs and pricing power.

| # | Data Layer | Value Add | New Buyer Segments |
|---|---|---|---|
| 1 | FCC/ITU regulatory filings | Spectrum alerts, orbital slot tracking | Space law firms, regulators |
| 2 | Constellation analytics | Growth tracking, deployment pace | Investors, equity analysts |
| 3 | Conjunction / debris risk | Collision probability, maneuver alerts | Operators, insurers, defense |
| 4 | Supply chain intelligence | Component tracking, vendor mapping | Manufacturers, procurement |

---

## Future Data Source Candidates

The MVP launches with two primary sources (Space-Track GP/SATCAT, UCS Satellite Database). FAA launch licenses were originally planned as a Phase A source but were dropped after investigation — the FAA does not publish structured launch data; their licenses authorize vehicles and sites but not specific missions or dates. Historical launches are instead derived from Space-Track's satellite catalog.

Upcoming launch tracking is the most significant data gap and should be prioritized in Phase C or revisited when discovery calls clarify buyer expectations.

| Source | What It Adds | Add When |
|---|---|---|
| Upcoming launch curation | Scheduled launches, payloads, target orbits | **Priority.** Revisit in Phase C. Sources include operator press releases, Spaceflight Now, NASA Spaceflight forums. Requires manual or semi-automated curation — no clean API exists. |
| CelesTrak | Real-time orbital data, supplementary TLEs | Users need fresher orbital updates than Space-Track alone provides |
| ITU filings | Spectrum allocation, orbital slot tracking | Regulatory/spectrum questions come up repeatedly in discovery calls |
| FAA/AST license filings | Signal that a launch is approved (but not when or what payload) | Only useful as a supplementary signal alongside other upcoming launch sources |
| SEC filings | Financial data on public operators | Investor persona demands company-level financial context |
| FCC IBFS | US spectrum licensing, earth station permits | Users need US-specific regulatory coverage |

---

## Key Risks to Monitor

| Risk | Likelihood | Mitigation |
|---|---|---|
| Buyers say "cool" but won't pay | Medium-high | Validate pricing in discovery calls, not after building |
| Data sources change or restrict access | Low-medium | Diversify sources early; manual curation as fallback |
| Incumbent (Seradata, Bryce) copies the API approach | Low near-term | Move fast; their sales cycles are slow and products are legacy |
| Scope creep pulls you toward dashboard/analytics too early | High | Strict rule: API only until 5 paying users |

---

## Bottom Line

This sprint costs under $350 and 10–15 hours per week alongside your day job. By Day 90 you will know whether this is a real business or an interesting idea. The single most important action in Week 1 is booking those discovery calls — everything else follows from what you learn in those conversations.
