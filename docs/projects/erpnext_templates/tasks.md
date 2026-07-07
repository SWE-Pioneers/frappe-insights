# Tasks — ERPNext Dashboard Templates

See [plan.md](./plan.md) for specs, design rules, and rationale.

## Day 1 — Environment + demo-data generator

- [x] Dev site with ERPNext (`erpnext2.localhost`; generator bootstraps the setup
      wizard on a bare site — company **Summit Supply Co**)
- [x] `scripts/erpnext_demo/generate.py` (`bench execute`, seeded RNG, parameterized):
  - [x] Masters: ~20 customers (Pareto skew), ~10 suppliers, ~50 items / ~6 groups,
        2 warehouses; fiscal years for full 18-month range
  - [x] Opening stock, then transactions submitted chronologically oldest-first
        (`set_posting_time = 1`) — never backdate into existing stock history
  - [x] Sales: SO → SI with growth + seasonality; customer payment-behavior classes
        (prompt/slow/delinquent) so AR ageing fills all buckets incl. 90+; partial
        payments; a few credit notes (`is_return`)
  - [x] Quotations: Open / Ordered / Lost mix with `order_lost_reason`
  - [x] Some SOs past `delivery_date` undelivered; POs past `schedule_date` unreceived
  - [x] Purchases: PO → PR → PI, receipts with varied delay vs `schedule_date`
  - [x] Stock: steady movers + a dead cluster (no movement 90/180+ days) + items below
        reorder level (Item Reorder set above current qty)
- [x] Run once (~3–5k docs), sanity-eyeball in ERPNext reports, `bench backup` →
      keep `.sql.gz` as instant-reset artifact (local, not in git)
      — 2026-07-07 run, seed 42: ~3.0k transactional docs, 0 failures; AR Summary /
      Stock Balance / Sales Analytics all reconcile exactly with the generated data;
      backup: `sites/erpnext2.localhost/private/backups/20260707_223305-*.sql.gz`

## Day 2 — Template backend + gallery UI (PR 1)

- [ ] `insights/workbook_templates/` layout: one folder per template with
      `manifest.json` + `workbook.json` + `preview.png`
- [ ] `insights/api/templates.py`:
  - [ ] `get_workbook_templates()` — manifest scan, `required_apps` filter against
        installed apps, has-data flag per template
  - [ ] `create_workbook_from_template(template_name)` — load JSON → `import_workbook()`
- [ ] Temporary hand-rolled seed template so API/UI are testable before real content
- [ ] "Start with a template" section on the workbook list
      (`frontend/src2/workbook/WorkbookList.vue`; the old Home page is unrouted dead
      code — `/` redirects to `/dashboards`) — cards with preview, title, description,
      module badge; frappe-ui components + tokens
- [ ] Renders only when endpoint returns templates (non-ERPNext sites see zero change)
- [ ] Click → confirm → create → route to new workbook
- [ ] Tests: endpoint hidden without ERPNext; create round-trips seed template;
      CI test parses every manifest + imports every committed `workbook.json`
- [ ] Pre-commit, review, **merge PR 1**

## Day 3 — Sales workbook

Establish the reusable patterns here: period-comparison number cards, funnel, action table.

- [ ] Number cards: Revenue (net), Invoice count, Avg invoice value, Active customers
- [ ] Revenue trend (Line, 12 mo)
- [ ] Top 10 customers (Row), Top 10 items (Row), Revenue by item group (Donut)
- [ ] Quotation funnel (Funnel: total → Ordered; Lost beside)
- [ ] Overdue deliveries action table (SO `per_delivered < 100`, `delivery_date < today`)
- [ ] Dashboard filters: date range + company
- [ ] Correctness: `docstatus = 1`, returns net out, base currency, POS caveat in description
- [ ] Export → prettify → commit + manifest + preview screenshot

## Day 4 — Purchasing workbook + start Accounting

- [ ] Purchasing (mirror Sales patterns): Spend, PO count, Avg PO value, Active suppliers
      cards; Spend trend; Spend by item group; Top 10 suppliers; PO status donut;
      Overdue POs action table
- [ ] Export + manifest + preview
- [ ] Accounting: decide ageing-bucket approach (builder `mutate` vs native SQL) — decide
      fast, don't burn hours
- [ ] AR ageing bar + AP ageing bar

## Day 5 — Finish Accounting (PR 2)

- [ ] Cards: Total AR, Total AP, % AR overdue, % AR > 90d, Net cash flow
- [ ] Top overdue customers table (collections call list)
- [ ] Payments due next 30 days table
- [ ] Cash in vs out (grouped bar, Payment Entry)
- [ ] Invoiced vs collected (grouped bar)
- [ ] Export + manifest + preview
- [ ] Review + **merge PR 2 (Sales + Purchasing)**

## Day 6 — Stock workbook

- [ ] Cards: Total stock value, Stock value change, Items below reorder level,
      Dead stock value (90d — needs SLE max-posting-date join)
- [ ] Stock value by warehouse (Bar), by item group (Bar)
- [ ] Stock ageing by value (last-movement buckets 0–30/31–90/91–180/180+; label proxy)
- [ ] In vs out (grouped bar, SLE, `is_cancelled = 0`)
- [ ] Reorder alert table (Bin ⋈ Item Reorder)
- [ ] Top items by stock value table (qty, value, days since last movement)
- [ ] Export + manifest + preview

## Day 7 — Verification + hardening (PR 3)

- [ ] `scripts/erpnext_demo/verify.py` — print template numbers next to the
      corresponding ERPNext report values (AR Summary, Stock Balance, Sales Analytics);
      all must match
- [ ] Import every template on a clean ERPNext site (zero rows) — every query executes
      without error, dashboards show empty states
- [ ] SQL/perf pass on heavy queries (SLE, ageing); add limits/filters where needed
- [ ] Permissions: gallery only for workbook creators; nothing leaks to viewer roles
- [ ] Docs note: what ships + how to contribute a template
- [ ] Review + **merge PR 3 (Accounting + Stock)**

## Fast-follows (🟡 — pre-specced in plan.md, ship on feedback)

- [ ] Sales: new vs returning revenue; gross margin % (with bundle/POS caveat)
- [ ] Purchasing: supplier on-time delivery % (PR Item ⋈ PO Item); price trend of top items
- [ ] Accounting: DSO card; income vs expense trend (GL ⋈ Account)
- [ ] Stock: days of cover

## Cut lines (if the week runs hot)

- Accounting: ship AR/AP without ageing buckets (outstanding totals + overdue lists only)
- Stock: drop stock ageing chart + dead-stock card, keep value/reorder views
- Do NOT cut Purchasing — it's a near-free clone of Sales
