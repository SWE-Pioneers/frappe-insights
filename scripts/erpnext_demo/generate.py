"""Deterministic ERPNext demo-data generator for the Insights dashboard templates.

Seeds a demo company with 18 months of sales / purchasing / accounting / stock
history whose *distributions* exercise every chart in
docs/projects/erpnext_templates/plan.md (growth + seasonality, AR ageing in all
buckets, quotation funnel, overdue SOs/POs, dead stock, reorder alerts, ...).

Usage (fresh site, ERPNext installed, setup wizard NOT required). `bench execute`
only resolves dotted paths inside installed apps, so import via the eval fallback
(run from the bench directory so apps/insights is on sys.path):

    bench --site <site> execute \
      "__import__('scripts.erpnext_demo.generate', fromlist=['run']).run"
    # smoke test at ~5% volume:
    bench --site <site> execute \
      "__import__('scripts.erpnext_demo.generate', fromlist=['run']).run" \
      --kwargs "{'scale': 0.05}"

Everything is driven by one seeded RNG — same seed + params => same dataset.
All stock-affecting documents are submitted chronologically oldest-first with
set_posting_time = 1, so no backdated entries and no repost storms.
"""

import heapq
import random
from datetime import timedelta

import frappe
from frappe.utils import add_days, add_months, flt, get_first_day, getdate

# ---------------------------------------------------------------- catalog ---

COMPANY = "Summit Supply Co"
ABBR = "SSC"
COUNTRY = "India"
CURRENCY = "INR"

# group: (items, cost range, order qty range)
CATALOG = {
    "Furniture": (
        [
            "Oak Office Desk",
            "Ergonomic Chair",
            "Walnut Bookshelf",
            "Conference Table",
            "Filing Cabinet",
            "Standing Desk",
            "Visitor Chair",
            "Coffee Table",
        ],
        (4000, 22000),
        (1, 6),
    ),
    "Electronics": (
        [
            "24in LED Monitor",
            "Wireless Keyboard",
            "USB-C Dock",
            "Laptop Stand",
            "Webcam 1080p",
            "Bluetooth Speaker",
            "Wireless Mouse",
            "HDMI Cable 2m",
            "Power Bank 20000mAh",
        ],
        (500, 15000),
        (1, 10),
    ),
    "Appliances": (
        [
            "Air Purifier",
            "Coffee Machine",
            "Water Dispenser",
            "Microwave Oven",
            "Ceiling Fan",
            "Vacuum Cleaner",
            "Induction Cooktop",
        ],
        (3000, 18000),
        (1, 5),
    ),
    "Stationery": (
        [
            "A4 Paper Ream",
            "Ballpoint Pen Box",
            "Heavy Duty Stapler",
            "Whiteboard Marker Set",
            "Sticky Notes Pack",
            "Ring Binder",
            "Envelope Pack 100",
            "Spiral Notebook",
        ],
        (50, 500),
        (5, 40),
    ),
    "Packaging": (
        [
            "Carton Box Large",
            "Carton Box Small",
            "Bubble Wrap Roll",
            "Packing Tape 6pk",
            "Stretch Film Roll",
            "Foam Sheet Pack",
            "Courier Bag 100pk",
        ],
        (100, 1500),
        (5, 30),
    ),
    "Lighting": (
        [
            "LED Panel 40W",
            "Desk Lamp",
            "LED Bulb 9W 10pk",
            "Track Light Kit",
            "Emergency Light",
            "Floor Lamp",
            "LED Strip 5m",
            "Pendant Light",
            "Tube Light 20W",
            "Solar Garden Light",
            "Wall Sconce",
        ],
        (200, 5000),
        (2, 12),
    ),
}

CUSTOMERS = [
    "Meridian Retail LLP",
    "Kova Interiors",
    "BlueStone Offices",
    "Zenwork Solutions",
    "Harbor & Co",
    "Trident Facilities",
    "Novakart Online",
    "Cedarline Hotels",
    "Paramount Estates",
    "Quill & Crate",
    "Vertex Coworking",
    "Silverbirch Schools",
    "Mosaic Studios",
    "Lakeshore Clinics",
    "Ironwood Manufacturing",
    "Sundial Cafes",
    "Crescent Logistics",
    "Alto Fintech",
    "Greenfield Grocers",
    "Orbit Events",
]

SUPPLIERS = [
    "Deccan Furnishings",
    "Volt Electronics Wholesale",
    "Apex Appliance Distributors",
    "Saraswati Paper Mills",
    "PackRight Industries",
    "Lumina Lighting Works",
    "Krishna Timber & Boards",
    "Omni Components",
    "Everest Trade House",
    "Coastal Imports",
]

GROUP_SUPPLIERS = {
    "Furniture": ["Deccan Furnishings", "Krishna Timber & Boards"],
    "Electronics": ["Volt Electronics Wholesale", "Omni Components"],
    "Appliances": ["Apex Appliance Distributors", "Coastal Imports"],
    "Stationery": ["Saraswati Paper Mills", "Everest Trade House"],
    "Packaging": ["PackRight Industries", "Everest Trade House"],
    "Lighting": ["Lumina Lighting Works", "Coastal Imports"],
}

LOST_REASONS = ["Price too high", "Chose competitor", "Project cancelled", "No response"]

SEASON = {
    1: 0.90,
    2: 0.95,
    3: 1.00,
    4: 0.85,
    5: 0.90,
    6: 0.95,
    7: 1.00,
    8: 1.00,
    9: 1.05,
    10: 1.20,
    11: 1.30,
    12: 1.25,
}

# payment behavior: class -> (credit_days, share of customers)
PAY_CLASSES = {"prompt": 15, "slow": 30, "delinquent": 45}

# event priorities: same-day ordering (receipts before deliveries etc.)
PRIO = {
    "opening": 0,
    "replenish": 1,
    "po": 2,
    "pr": 3,
    "pi": 4,
    "quote": 5,
    "so": 6,
    "dn": 7,
    "si": 8,
    "cn": 9,
    "pay_in": 10,
    "pay_out": 11,
}


def _imp(*paths):
    for p in paths:
        try:
            return frappe.get_attr(p)
        except Exception:
            continue
    frappe.throw(f"None of {paths} importable")


# ------------------------------------------------------------------ entry ---


def run(seed=42, months=18, scale=1.0, end_date=None, force=False):
    rng = random.Random(seed)
    end = getdate(end_date) if end_date else getdate()
    start = get_first_day(add_months(end, -(months - 1)))

    if frappe.db.count("Sales Invoice") and not force:
        frappe.throw("Site already has Sales Invoices. Run on a fresh site (or pass force=True).")

    frappe.flags.mute_emails = True

    print(f"Generating demo data: {start} → {end}, seed={seed}, scale={scale}")
    _bootstrap(start, end)
    cat = _make_masters(rng, end)
    frappe.db.commit()

    gen = _Generator(rng, cat, start, end, scale)
    gen.walk()
    frappe.db.commit()

    _set_reorder_levels(rng, cat)
    frappe.db.commit()

    _summary(end)
    print(
        "\nDone. Now take a backup as the instant-reset artifact:\n"
        f"  bench --site {frappe.local.site} backup"
    )


# -------------------------------------------------------------- bootstrap ---


def _bootstrap(start, end):
    if not frappe.db.exists("Company", COMPANY):
        if frappe.db.get_all("Company", limit=1):
            frappe.throw("A different Company already exists on this site — refusing to mix data.")
        from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

        fy_start, fy_end = _fy_bounds(end)
        print("Running setup wizard ...")
        setup_complete(
            {
                "language": "English",
                "country": COUNTRY,
                "timezone": "Asia/Kolkata",
                "currency": CURRENCY,
                "company_name": COMPANY,
                "company_abbr": ABBR,
                "chart_of_accounts": "Standard",
                "fy_start_date": str(fy_start),
                "fy_end_date": str(fy_end),
                "setup_demo": 0,
            }
        )
        frappe.db.commit()

    # fiscal years for the whole range (+ a little slack on both sides)
    d = add_days(start, -45)
    while d <= add_days(end, 45):
        fy_start, fy_end = _fy_bounds(d)
        year = f"{fy_start.year}-{fy_end.year}"
        if not frappe.db.exists("Fiscal Year", year):
            frappe.get_doc(
                {
                    "doctype": "Fiscal Year",
                    "year": year,
                    "year_start_date": fy_start,
                    "year_end_date": fy_end,
                }
            ).insert(ignore_permissions=True)
            print(f"Created Fiscal Year {year}")
        d = add_days(fy_end, 1)

    # a leaf Bank account so get_payment_entry always finds one
    bank = f"Demo Bank - {ABBR}"
    if not frappe.db.exists("Account", bank):
        parent = frappe.db.get_value(
            "Account", {"company": COMPANY, "account_type": "Bank", "is_group": 1}, "name"
        ) or frappe.db.get_value("Account", {"company": COMPANY, "root_type": "Asset", "is_group": 1}, "name")
        frappe.get_doc(
            {
                "doctype": "Account",
                "account_name": "Demo Bank",
                "company": COMPANY,
                "parent_account": parent,
                "account_type": "Bank",
                "account_currency": CURRENCY,
            }
        ).insert(ignore_permissions=True)

    # historical quotations must be convertible to SOs
    frappe.db.set_single_value("Selling Settings", "allow_sales_order_creation_for_expired_quotation", 1)

    for reason in LOST_REASONS:
        if not frappe.db.exists("Quotation Lost Reason", reason):
            frappe.get_doc({"doctype": "Quotation Lost Reason", "order_lost_reason": reason}).insert(
                ignore_permissions=True
            )


def _fy_bounds(d):
    """Indian fiscal year (Apr-Mar) containing date d."""
    d = getdate(d)
    y = d.year if d.month >= 4 else d.year - 1
    return getdate(f"{y}-04-01"), getdate(f"{y + 1}-03-31")


# ---------------------------------------------------------------- masters ---


def _leaf(doctype):
    return frappe.db.get_value(doctype, {"is_group": 0}, "name")


def _make_masters(rng, end):
    print("Creating masters ...")
    cat = frappe._dict(item_meta={}, customer_meta={}, suppliers=list(SUPPLIERS))

    for group in CATALOG:
        if not frappe.db.exists("Item Group", group):
            frappe.get_doc(
                {
                    "doctype": "Item Group",
                    "item_group_name": group,
                    "parent_item_group": "All Item Groups",
                    "is_group": 0,
                }
            ).insert(ignore_permissions=True)

    cg, terr, sg = _leaf("Customer Group"), _leaf("Territory"), _leaf("Supplier Group")

    for name in SUPPLIERS:
        if not frappe.db.exists("Supplier", name):
            frappe.get_doc(
                {
                    "doctype": "Supplier",
                    "supplier_name": name,
                    "supplier_group": sg,
                    "supplier_type": "Company",
                    "country": COUNTRY,
                }
            ).insert(ignore_permissions=True)

    # customers: Pareto weight by rank + payment-behavior class
    classes = ["prompt"] * 10 + ["slow"] * 6 + ["delinquent"] * 4
    rng.shuffle(classes)
    ranks = list(range(1, len(CUSTOMERS) + 1))
    rng.shuffle(ranks)
    for name, rank, cls in zip(CUSTOMERS, ranks, classes, strict=True):
        if not frappe.db.exists("Customer", name):
            frappe.get_doc(
                {
                    "doctype": "Customer",
                    "customer_name": name,
                    "customer_group": cg,
                    "territory": terr,
                    "customer_type": "Company",
                }
            ).insert(ignore_permissions=True)
        cat.customer_meta[name] = frappe._dict(weight=1.0 / rank**0.9, pay_class=cls)

    warehouses = [f"Stores - {ABBR}", f"Finished Goods - {ABBR}"]
    for wh in warehouses:
        if not frappe.db.exists("Warehouse", wh):
            frappe.throw(f"Expected warehouse {wh} from company setup")

    # items: cost, price, home warehouse, supplier, popularity, dead-cluster cutoff
    all_items = [(n, g) for g, (names, _, _) in CATALOG.items() for n in names]
    pop_ranks = list(range(1, len(all_items) + 1))
    rng.shuffle(pop_ranks)
    dead = rng.sample(range(len(all_items)), 12)
    dead_a, dead_b = set(dead[:8]), set(dead[8:])  # no movement 180+/90+ days

    for idx, (name, group) in enumerate(all_items):
        lo, hi = CATALOG[group][1]
        cost = round(rng.uniform(lo, hi), -1) or lo
        cutoff = None
        if idx in dead_a:
            cutoff = add_days(end, -rng.randint(200, 330))
        elif idx in dead_b:
            cutoff = add_days(end, -rng.randint(100, 160))
        wh = warehouses[0] if rng.random() < 0.6 else warehouses[1]
        supplier = GROUP_SUPPLIERS[group][0 if rng.random() < 0.8 else 1]

        if not frappe.db.exists("Item", name):
            frappe.get_doc(
                {
                    "doctype": "Item",
                    "item_code": name,
                    "item_name": name,
                    "item_group": group,
                    "stock_uom": "Nos",
                    "is_stock_item": 1,
                    "valuation_method": "FIFO",
                    "item_defaults": [
                        {"company": COMPANY, "default_warehouse": wh, "default_supplier": supplier}
                    ],
                }
            ).insert(ignore_permissions=True)

        qlo, qhi = CATALOG[group][2]
        cat.item_meta[name] = frappe._dict(
            group=group,
            cost=cost,
            price=round(cost * rng.uniform(1.3, 1.6), -1),
            warehouse=wh,
            supplier=supplier,
            weight=1.0 / pop_ranks[idx] ** 0.7,
            qty_range=(qlo, qhi),
            cutoff=cutoff,
        )

    print(f"  {len(cat.item_meta)} items, {len(cat.customer_meta)} customers, {len(SUPPLIERS)} suppliers")
    return cat


# ---------------------------------------------------------------- engine ----


class _Generator:
    def __init__(self, rng, cat, start, end, scale):
        self.rng, self.cat, self.start, self.end, self.scale = rng, cat, start, end, scale
        self.heap, self.seq = [], 0
        self.stock = {i: 0 for i in cat.item_meta}  # simulated on-hand (reserved at SO time)
        self.time_idx = {}  # per-date posting-time counter
        self.counts, self.failures = {}, 0
        self.pe_seq = 0
        self.years = lambda d: (getdate(d) - start).days / 365.0

    # -- helpers ------------------------------------------------------------

    def push(self, date, kind, payload):
        if getdate(date) > self.end:
            return
        self.seq += 1
        heapq.heappush(self.heap, (getdate(date), PRIO[kind], self.seq, kind, payload))

    def stamp(self, doc, date):
        """set_posting_time + monotonically increasing time within a day"""
        idx = self.time_idx.get(date, 0)
        self.time_idx[date] = idx + 1
        doc.set_posting_time = 1
        doc.posting_date = date
        doc.posting_time = str(timedelta(hours=9) + timedelta(minutes=3 * min(idx, 170)))

    def sell_rate(self, item):
        infl = 1 + 0.06 * self.years(getattr(self, "_cur_date", self.start))
        return round(self.cat.item_meta[item].price * infl * self.rng.uniform(0.97, 1.03), 0)

    def buy_rate(self, item, date):
        infl = 1 + 0.08 * self.years(date)
        return round(self.cat.item_meta[item].cost * infl * self.rng.uniform(0.97, 1.03), 0)

    def allowed(self, item, date):
        c = self.cat.item_meta[item].cutoff
        return c is None or getdate(date) <= c

    # -- planning -----------------------------------------------------------

    def walk(self):
        self.push(self.start, "opening", {})
        self.plan_sales()
        for i in range(0, 220):
            d = add_months(self.start, i)
            if d > self.end:
                break
            self.push(d, "replenish", {"month": i})

        total_hint = len(self.heap)
        print(f"Planned {total_hint} seed events; executing chronologically ...")
        n = 0
        while self.heap:
            date, _prio, _seq, kind, payload = heapq.heappop(self.heap)
            self._cur_date = date
            try:
                frappe.db.savepoint("demo_evt")
                getattr(self, "on_" + kind)(date, payload)
                self.counts[kind] = self.counts.get(kind, 0) + 1
            except Exception as e:
                frappe.db.rollback(save_point="demo_evt")
                self.failures += 1
                print(f"  !! {kind} on {date} failed: {frappe.utils.cstr(e)[:200]}")
                if self.failures > 50:
                    raise
            n += 1
            if n % 50 == 0:
                frappe.db.commit()
            if n % 200 == 0:
                print(
                    f"  [{n}] at {date} :: " + ", ".join(f"{k}={v}" for k, v in sorted(self.counts.items()))
                )
        frappe.db.commit()
        print(
            "Event counts: "
            + ", ".join(f"{k}={v}" for k, v in sorted(self.counts.items()))
            + f", failures={self.failures}"
        )

    def plan_sales(self):
        rng, months = self.rng, []
        i = 0
        while True:
            d = add_months(self.start, i)
            if d > self.end:
                break
            months.append((i, d))
            i += 1

        for i, mstart in months:
            n = max(1, round(self.scale * 26 * (1.032**i) * SEASON[mstart.month]))
            for _ in range(n):
                self.plan_chain(mstart, from_quote=rng.random() < 0.45)
            for _ in range(round(n * 0.25) or 1):
                self.plan_quote_only(mstart, "lost")
            for _ in range(round(n * 0.12)):
                self.plan_quote_only(mstart, "open")

    def _chain_lines(self, date):
        rng = self.rng
        pool = [i for i in self.cat.item_meta if self.allowed(i, date)]
        weights = [self.cat.item_meta[i].weight for i in pool]
        n_lines = rng.choices([1, 2, 3, 4], [0.35, 0.35, 0.2, 0.1])[0]
        lines, seen = [], set()
        for item in rng.choices(pool, weights=weights, k=n_lines):
            if item in seen:
                continue
            seen.add(item)
            qlo, qhi = self.cat.item_meta[item].qty_range
            lines.append([item, rng.randint(qlo, qhi)])
        return lines

    def plan_chain(self, mstart, from_quote):
        rng = self.rng
        so_date = min(add_days(mstart, rng.randint(0, 27)), self.end)
        customer = rng.choices(
            list(self.cat.customer_meta), weights=[c.weight for c in self.cat.customer_meta.values()]
        )[0]
        chain = frappe._dict(
            customer=customer,
            lines=self._chain_lines(so_date),
            so_date=so_date,
            delivery_date=add_days(so_date, rng.randint(3, 14)),
        )
        if not chain.lines:
            return
        if from_quote:
            qdate = max(self.start, add_days(so_date, -rng.randint(2, 10)))
            self.push(qdate, "quote", {"chain": chain, "fate": "ordered", "date": qdate})
        self.push(so_date, "so", {"chain": chain})

        if rng.random() < 0.11:
            return  # never delivered -> overdue SO once delivery_date passes
        dn_date = add_days(chain.delivery_date, rng.randint(-2, 12))
        if dn_date > self.end:
            return
        self.push(dn_date, "dn", {"chain": chain})
        si_date = add_days(dn_date, rng.randint(0, 4))
        if si_date > self.end:
            return
        self.push(si_date, "si", {"chain": chain})
        self.plan_payments(chain, si_date)
        if rng.random() < 0.025:
            self.push(add_days(si_date, rng.randint(4, 15)), "cn", {"chain": chain})

    def plan_payments(self, chain, si_date):
        rng = self.rng
        cls = self.cat.customer_meta[chain.customer].pay_class
        due = add_days(si_date, PAY_CLASSES[cls])
        chain.due_date = due
        plans = []
        if cls == "prompt":
            plans = [(add_days(si_date, rng.randint(3, 15)), 1.0)]
        elif cls == "slow":
            if rng.random() < 0.6:
                frac = rng.uniform(0.4, 0.7)
                plans = [(add_days(due, rng.randint(5, 30)), frac), (add_days(due, rng.randint(35, 75)), 1.0)]
            else:
                plans = [(add_days(due, rng.randint(10, 50)), 1.0)]
        else:  # delinquent
            r = rng.random()
            if r < 0.4:
                plans = []
            elif r < 0.7:
                plans = [(add_days(due, rng.randint(40, 100)), rng.uniform(0.3, 0.6))]
            else:
                plans = [(add_days(due, rng.randint(60, 120)), 1.0)]
        for pdate, frac in plans:
            self.push(pdate, "pay_in", {"chain": chain, "frac": frac})

    def plan_quote_only(self, mstart, fate):
        rng = self.rng
        qdate = min(add_days(mstart, rng.randint(0, 27)), self.end)
        chain = frappe._dict(
            customer=rng.choices(
                list(self.cat.customer_meta), weights=[c.weight for c in self.cat.customer_meta.values()]
            )[0],
            lines=self._chain_lines(qdate),
        )
        if chain.lines:
            self.push(qdate, "quote", {"chain": chain, "fate": fate, "date": qdate})

    # -- handlers -----------------------------------------------------------

    def on_opening(self, date, payload):
        rng = self.rng
        by_wh = {}
        for item, meta in self.cat.item_meta.items():
            if meta.cutoff:
                qty = rng.randint(40, 100)
            else:
                qty = int(self.par(item) * 1.8) + 10
            by_wh.setdefault(meta.warehouse, []).append((item, qty))
        for wh, rows in by_wh.items():
            se = frappe.get_doc(
                {
                    "doctype": "Stock Entry",
                    "company": COMPANY,
                    "stock_entry_type": "Material Receipt",
                    "to_warehouse": wh,
                    "items": [
                        {
                            "item_code": i,
                            "qty": q,
                            "t_warehouse": wh,
                            "basic_rate": self.cat.item_meta[i].cost,
                            "uom": "Nos",
                            "conversion_factor": 1,
                        }
                        for i, q in rows
                    ],
                }
            )
            self.stamp(se, date)
            se.insert(ignore_permissions=True)
            se.submit()
            for i, q in rows:
                self.stock[i] += q
        print(f"  opening stock posted on {date}")

    def par(self, item):
        """target on-hand level ~= 2.5x expected monthly demand"""
        meta = self.cat.item_meta[item]
        total_w = sum(m.weight for m in self.cat.item_meta.values())
        monthly_orders = self.scale * 26 * 1.4 * 2.2 * (meta.weight / total_w)
        avg_qty = sum(meta.qty_range) / 2
        return max(20 * self.scale, monthly_orders * avg_qty * 2.5)

    def on_replenish(self, date, payload):
        rng = self.rng
        by_supplier = {}
        for item, meta in self.cat.item_meta.items():
            if not self.allowed(item, add_days(date, 15)):
                continue
            if self.stock[item] < self.par(item):
                qty = int(self.par(item) * 2 - self.stock[item])
                qty = max(5, int(round(qty / 5.0) * 5))
                by_supplier.setdefault(meta.supplier, []).append((item, qty))
        for supplier, rows in by_supplier.items():
            po_date = min(add_days(date, rng.randint(0, 5)), self.end)
            plan = frappe._dict(supplier=supplier, rows=rows, schedule=add_days(po_date, rng.randint(7, 20)))
            self.push(po_date, "po", {"plan": plan})

            received = rng.random() > 0.06 or payload["month"] == 0
            if not received:
                continue  # overdue unreceived PO
            r = rng.random()
            delay = rng.randint(-3, 0) if r < 0.4 else rng.randint(1, 10) if r < 0.85 else rng.randint(11, 30)
            pr_date = add_days(plan.schedule, delay)
            if pr_date > self.end:
                continue  # still in transit
            self.push(pr_date, "pr", {"plan": plan})
            if rng.random() < 0.9:
                pi_date = add_days(pr_date, rng.randint(0, 10))
                if pi_date <= self.end:
                    self.push(pi_date, "pi", {"plan": plan})
                    if rng.random() < 0.85:
                        self.push(add_days(pi_date, rng.randint(10, 45)), "pay_out", {"plan": plan})

    def on_quote(self, date, payload):
        chain, rng = payload["chain"], self.rng
        q = frappe.get_doc(
            {
                "doctype": "Quotation",
                "company": COMPANY,
                "quotation_to": "Customer",
                "party_name": chain.customer,
                "transaction_date": date,
                "valid_till": add_days(date, 30),
                "currency": CURRENCY,
                "conversion_rate": 1,
                "selling_price_list": "Standard Selling",
                "ignore_pricing_rule": 1,
                "items": [
                    {
                        "item_code": i,
                        "qty": q_,
                        "rate": self.sell_rate(i),
                        "uom": "Nos",
                        "conversion_factor": 1,
                    }
                    for i, q_ in chain.lines
                ],
            }
        )
        q.insert(ignore_permissions=True)
        q.submit()
        chain.quotation = q.name
        chain.quote_rates = {r.item_code: r.rate for r in q.items}
        if payload["fate"] == "lost":
            q.declare_enquiry_lost(
                [{"lost_reason": rng.choice(LOST_REASONS)}],
                [],
                detailed_reason=rng.choice(LOST_REASONS),
            )

    def on_so(self, date, payload):
        chain = payload["chain"]
        # clamp against simulated stock; reserve at SO time
        lines = []
        for item, qty in chain.lines:
            take = min(qty, int(self.stock[item]))
            if take > 0:
                lines.append((item, take))
                self.stock[item] -= take
        if not lines:
            return
        chain.lines = [list(l) for l in lines]

        if chain.get("quotation"):
            make_so = _imp(
                "erpnext.selling.doctype.quotation.mapper.make_sales_order",
                "erpnext.selling.doctype.quotation.quotation.make_sales_order",
            )
            so = make_so(chain.quotation)
            so.items = [r for r in so.items if r.item_code in dict(lines)]
            for r in so.items:
                r.qty = dict(lines)[r.item_code]
        else:
            so = frappe.get_doc(
                {
                    "doctype": "Sales Order",
                    "company": COMPANY,
                    "customer": chain.customer,
                    "currency": CURRENCY,
                    "conversion_rate": 1,
                    "selling_price_list": "Standard Selling",
                    "ignore_pricing_rule": 1,
                    "items": [
                        {
                            "item_code": i,
                            "qty": q,
                            "rate": self.sell_rate(i),
                            "uom": "Nos",
                            "conversion_factor": 1,
                        }
                        for i, q in lines
                    ],
                }
            )
        so.transaction_date = date
        so.delivery_date = chain.delivery_date
        for r in so.items:
            r.delivery_date = chain.delivery_date
        so.insert(ignore_permissions=True)
        so.submit()
        chain.so = so.name

    def on_dn(self, date, payload):
        chain = payload["chain"]
        if not chain.get("so"):
            return
        make_dn = _imp(
            "erpnext.selling.doctype.sales_order.mapper.make_delivery_note",
            "erpnext.selling.doctype.sales_order.sales_order.make_delivery_note",
        )
        dn = make_dn(chain.so)
        self.stamp(dn, date)
        dn.insert(ignore_permissions=True)
        dn.submit()
        chain.dn = dn.name

    def on_si(self, date, payload):
        chain = payload["chain"]
        if not chain.get("dn"):
            return
        make_si = _imp(
            "erpnext.stock.doctype.delivery_note.mapper.make_sales_invoice",
            "erpnext.stock.doctype.delivery_note.delivery_note.make_sales_invoice",
        )
        si = make_si(chain.dn)
        self.stamp(si, date)
        si.due_date = max(chain.due_date, date)
        si.payment_schedule = []
        si.insert(ignore_permissions=True)
        si.submit()
        chain.si = si.name

    def on_cn(self, date, payload):
        chain = payload["chain"]
        if not chain.get("si"):
            return
        make_return = _imp("erpnext.controllers.sales_and_purchase_return.make_return_doc")
        cn = make_return("Sales Invoice", chain.si)
        cn.items = cn.items[:1]
        row = cn.items[0]
        row.qty = -max(1, int(abs(row.qty) * 0.4))
        self.stamp(cn, date)
        cn.due_date = date
        cn.payment_schedule = []
        cn.insert(ignore_permissions=True)
        cn.submit()

    def on_pay_in(self, date, payload):
        chain, frac = payload["chain"], payload["frac"]
        if not chain.get("si"):
            return
        self._pay("Sales Invoice", chain.si, date, frac)

    def on_pay_out(self, date, payload):
        plan = payload["plan"]
        if not plan.get("pi"):
            return
        frac = 1.0 if self.rng.random() > 0.15 else self.rng.uniform(0.4, 0.7)
        self._pay("Purchase Invoice", plan.pi, date, frac)

    def _pay(self, dt, dn, date, frac):
        outstanding = flt(frappe.db.get_value(dt, dn, "outstanding_amount"))
        if outstanding < 1:
            return
        get_payment_entry = _imp("erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry")
        pe = get_payment_entry(dt, dn)
        pe.posting_date = date
        self.pe_seq += 1
        pe.reference_no = f"DEMO-{self.pe_seq:05d}"
        pe.reference_date = date
        if frac < 0.999:
            alloc = min(outstanding, round(outstanding * frac, 0)) or outstanding
            pe.paid_amount = alloc
            pe.received_amount = alloc
            pe.references[0].allocated_amount = alloc
        pe.insert(ignore_permissions=True)
        pe.submit()

    def on_po(self, date, payload):
        plan = payload["plan"]
        po = frappe.get_doc(
            {
                "doctype": "Purchase Order",
                "company": COMPANY,
                "supplier": plan.supplier,
                "transaction_date": date,
                "schedule_date": plan.schedule,
                "currency": CURRENCY,
                "conversion_rate": 1,
                "buying_price_list": "Standard Buying",
                "ignore_pricing_rule": 1,
                "items": [
                    {
                        "item_code": i,
                        "qty": q,
                        "rate": self.buy_rate(i, date),
                        "schedule_date": plan.schedule,
                        "uom": "Nos",
                        "conversion_factor": 1,
                        "warehouse": self.cat.item_meta[i].warehouse,
                    }
                    for i, q in plan.rows
                ],
            }
        )
        po.insert(ignore_permissions=True)
        po.submit()
        plan.po = po.name

    def on_pr(self, date, payload):
        plan = payload["plan"]
        if not plan.get("po"):
            return
        make_pr = _imp(
            "erpnext.buying.doctype.purchase_order.mapper.make_purchase_receipt",
            "erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_receipt",
        )
        pr = make_pr(plan.po)
        self.stamp(pr, date)
        pr.insert(ignore_permissions=True)
        pr.submit()
        plan.pr = pr.name
        for r in pr.items:
            self.stock[r.item_code] = self.stock.get(r.item_code, 0) + r.qty

    def on_pi(self, date, payload):
        plan = payload["plan"]
        if not plan.get("pr"):
            return
        make_pi = _imp(
            "erpnext.stock.doctype.purchase_receipt.mapper.make_purchase_invoice",
            "erpnext.stock.doctype.purchase_receipt.purchase_receipt.make_purchase_invoice",
        )
        pi = make_pi(plan.pr)
        self.stamp(pi, date)
        pi.due_date = add_days(date, 30)
        pi.payment_schedule = []
        pi.bill_no = f"BILL-{plan.pr}"
        pi.bill_date = date
        pi.insert(ignore_permissions=True)
        pi.submit()
        plan.pi = pi.name


# ----------------------------------------------------------------- fixups ---


def _set_reorder_levels(rng, cat):
    """Item Reorder above current qty for a few steady movers -> reorder alerts."""
    movers = [i for i, m in cat.item_meta.items() if not m.cutoff]
    picks = rng.sample(movers, min(6, len(movers)))
    for item in picks:
        wh = cat.item_meta[item].warehouse
        bin_ = frappe.db.get_value(
            "Bin", {"item_code": item, "warehouse": wh}, ["actual_qty", "projected_qty"], as_dict=True
        )
        if not bin_:
            continue
        level = int(max(bin_.actual_qty, bin_.projected_qty)) + rng.randint(20, 60)
        doc = frappe.get_doc("Item", item)
        if doc.get("reorder_levels"):
            continue
        doc.append(
            "reorder_levels",
            {
                "warehouse": wh,
                "warehouse_reorder_level": level,
                "warehouse_reorder_qty": max(50, level // 2),
                "material_request_type": "Purchase",
            },
        )
        doc.save(ignore_permissions=True)
        print(f"  reorder level {level} set on {item} @ {wh}")


# ---------------------------------------------------------------- summary ---


def _summary(end):
    print("\n=== Summary ===")
    for dt in [
        "Quotation",
        "Sales Order",
        "Delivery Note",
        "Sales Invoice",
        "Payment Entry",
        "Purchase Order",
        "Purchase Receipt",
        "Purchase Invoice",
        "Stock Entry",
        "Customer",
        "Supplier",
        "Item",
    ]:
        print(f"  {dt}: {frappe.db.count(dt)}")

    ar = frappe.db.sql(
        """select sum(outstanding_amount) from `tabSales Invoice`
           where docstatus=1 and outstanding_amount > 0"""
    )[0][0]
    ap = frappe.db.sql(
        """select sum(outstanding_amount) from `tabPurchase Invoice`
           where docstatus=1 and outstanding_amount > 0"""
    )[0][0]
    stock_value = frappe.db.sql("select sum(stock_value) from `tabBin`")[0][0]
    negative = frappe.db.sql("select count(*) from `tabBin` where actual_qty < 0")[0][0]
    lost = frappe.db.count("Quotation", {"status": "Lost"})
    print(f"  Total AR outstanding: {flt(ar):,.0f}")
    print(f"  Total AP outstanding: {flt(ap):,.0f}")
    print(f"  Total stock value:    {flt(stock_value):,.0f}")
    print(f"  Lost quotations:      {lost}")
    print(f"  Bins with negative qty (must be 0): {negative}")

    buckets = frappe.db.sql(
        """select
             sum(if(due_date >= %(today)s, outstanding_amount, 0)) as not_due,
             sum(if(due_date < %(today)s and datediff(%(today)s, due_date) <= 30, outstanding_amount, 0)) as b30,
             sum(if(datediff(%(today)s, due_date) between 31 and 60, outstanding_amount, 0)) as b60,
             sum(if(datediff(%(today)s, due_date) between 61 and 90, outstanding_amount, 0)) as b90,
             sum(if(datediff(%(today)s, due_date) > 90, outstanding_amount, 0)) as b90p
           from `tabSales Invoice`
           where docstatus = 1 and outstanding_amount > 0""",
        {"today": end},
        as_dict=True,
    )[0]
    print(
        "  AR ageing buckets (not-due / 1-30 / 31-60 / 61-90 / 90+): "
        f"{flt(buckets.not_due):,.0f} / {flt(buckets.b30):,.0f} / {flt(buckets.b60):,.0f}"
        f" / {flt(buckets.b90):,.0f} / {flt(buckets.b90p):,.0f}"
    )
