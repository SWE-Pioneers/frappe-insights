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

- [x] Purchasing (mirror Sales patterns): Spend, PO count, Avg PO value, Active suppliers
      cards; Spend trend; Spend by item group; Top 10 suppliers; PO status donut;
      Overdue POs action table
- [x] Export + manifest (`insights/workbook_templates/purchasing/`) — "Purchasing
      Overview": 4 builder queries / 7 charts / 1 dashboard. All-builder (no native
      SQL), mirroring Sales. KPIs split across two number cards by source since Spend is
      invoice-based but order metrics are PO-based: Spend + Active Suppliers on Purchase
      Invoice (posting_date); PO Count + Avg PO Value on Purchase Order (transaction_date).
      Spend/top-suppliers = PI `base_net_total` (net of returns); item-group donut = PI
      Item `base_net_amount` (join to PI for posting_date/company); PO-status donut =
      count by `status`; overdue table = PO `per_received < 100` & `schedule_date <
      today()`, `days_late = date_diff(today(), schedule_date, "day")`. Date filter drives
      the performance charts (KPIs/trend/top-N/item-group); Company filters everything;
      PO-status + overdue are current views, not date-filtered (mirrors Sales'
      funnel/overdue). Validated by importing into erpnext2.localhost + executing every
      base query (67 PI / 114 PI Item / 85 PO / 4 overdue). Reconciles with ERPNext:
      Spend 23,321,010; Active Suppliers 10; PO Count 85; Avg PO Value 326,004; PO status
      67/10/8; overdue days-late 390/166/25/24. **preview.png pending** — capture during
      the UI verify pass. NOT committed.
- [x] Accounting: decide ageing-bucket approach — **builder pipeline, no native SQL**.
      (First cut used native SQL; reworked to all-builder so imported queries stay
      UI-editable + permission-aware, matching Sales/Stock convention.) GL-based
      outstanding = source GL Entry → filter `is_cancelled=0`/party/voucher-type →
      summarize `sum(debit)-sum(credit)` by `against_voucher` → filter `> 0.5`
      (rounding cutoff) → join back to the invoice → `mutate` days_overdue
      (`date_diff(today(), due_date, 'day')`) + bucket (`cases(...)`). One per-invoice
      AR/AP query feeds the ageing bar + cards + tables (DRY), company-filterable
      because charts do their own summarize.
- [x] AR ageing bar + AP ageing bar

## Day 5 — Finish Accounting (PR 2)

- [x] Cards: Total AR (7,494,343), Total AP (2,915,915), % AR overdue (71.9%),
      % AR > 90d (30.5%), Net cash flow (9,560,547) — all reconcile with the oracle.
      No period-over-period delta on cards (point-in-time AR history is v2, per plan).
- [x] Top overdue customers table (collections call list)
- [x] Payments due next 30 days table (filter `days_until_due <= 30`, so it also
      surfaces already-overdue payables the treasury still has to cover)
- [x] Cash in vs out (grouped bar, Payment Entry)
- [x] Invoiced vs collected (grouped bar)
- [x] Export + manifest (`insights/workbook_templates/accounting/`); dashboard filters
      = Company (all charts) + Date (cash-flow trends only, so AR/AP snapshots keep
      matching AR Summary). **preview.png pending** — capture during the UI verify pass.
- [ ] Review + **merge PR 2 (Sales + Purchasing)**

## Day 6 — Stock workbook

- [x] Cards: Total stock value, Stock value change, Items below reorder level,
      Dead stock value (90d — needs SLE max-posting-date join)
- [x] Stock value by warehouse (Bar), by item group (Bar)
- [x] Stock ageing by value (last-movement buckets 0–30/31–90/91–180/180+; label proxy)
- [x] In vs out (grouped bar, SLE, `is_cancelled = 0`)
- [x] Reorder alert table (Bin ⋈ Item Reorder)
- [x] Top items by stock value table (qty, value, days since last movement)
- [x] Export + manifest + preview
      — `insights/workbook_templates/erpnext_stock/` ("Inventory Health": 5 queries /
      10 charts / 1 dashboard + preview.png). Authored as workbook.json and validated by
      importing into erpnext2.localhost + executing every chart's data_query (mirroring
      the frontend). Reconciles with ERPNext: total stock value 16,445,986; by-warehouse
      10.01M / 6.43M; below-reorder 6; dead stock (90d+) 3,989,883; ageing
      12.13M / 323K / 650K / 3.34M. Dead-stock/ageing/top-items share an item-level
      max(posting_date) sub-query joined to Bin; reorder uses a two-column join_expression
      (Bin.item_code=parent & warehouse=warehouse) + column-vs-column filter. Note:
      `date_diff` is `col−other`, so days-since = `date_diff(today(), last_movement_date,
      "day")`. Base queries kept at raw grain so the date/company/warehouse dashboard
      filters apply; Date filter defaults to "Last 12 Months". Filter-link remapping,
      `within` filter, and the PR-1 CI import guard all verified. NOT committed —
      awaiting UI verification.

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
