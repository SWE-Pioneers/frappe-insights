import json
import os
from unittest.mock import patch

import frappe

from insights.api.templates import (
    MANIFEST_REQUIRED_KEYS,
    create_workbook_from_template,
    get_template_manifest,
    get_template_names,
    get_template_workbook,
    get_templates_path,
    get_workbook_templates,
)
from insights.insights.doctype.insights_workbook.insights_workbook import import_workbook
from insights.tests.base import InsightsIntegrationTestCase
from insights.tests.factories import USER_1, create_test_user, delete_users
from insights.tests.workbook_utils import cleanup_test_workbooks, get_workbook

SEED_TEMPLATE = "erpnext_sales_seed"

APPS_WITHOUT_ERPNEXT = ["frappe", "insights"]
APPS_WITH_ERPNEXT = ["frappe", "insights", "erpnext"]


def installed_apps(apps):
    # patch our narrow seam, not the global — patching frappe.get_installed_apps
    # breaks other apps' insert hooks on multi-app sites
    return patch("insights.api.templates.get_installed_apps", return_value=set(apps))


class TestWorkbookTemplates(InsightsIntegrationTestCase):
    COMMIT_AFTER_TEST_SETUP = True
    COMMIT_AFTER_TEST_TEARDOWN = True

    @classmethod
    def before_class(cls):
        cleanup_test_workbooks(USER_1)
        delete_users(USER_1)
        create_test_user(USER_1)

    @classmethod
    def after_class(cls):
        cleanup_test_workbooks(USER_1)
        delete_users(USER_1)

    def after_test(self):
        cleanup_test_workbooks(USER_1)

    def test_templates_hidden_when_required_apps_missing(self):
        with self.as_user(USER_1), installed_apps(APPS_WITHOUT_ERPNEXT):
            self.assertEqual(get_workbook_templates(), [])

    def test_templates_listed_when_required_apps_installed(self):
        with self.as_user(USER_1), installed_apps(APPS_WITH_ERPNEXT):
            templates = {t["name"]: t for t in get_workbook_templates()}

        self.assertIn(SEED_TEMPLATE, templates)
        seed = templates[SEED_TEMPLATE]
        self.assertEqual(seed["title"], "Sales Overview")
        self.assertEqual(seed["module"], "Selling")
        self.assertIn("has_data", seed)
        self.assertIsNone(seed["imported_workbook"])
        self.assertTrue(seed["preview_image"].startswith("data:image/png;base64,"))

    def test_imported_template_is_marked_and_disabled(self):
        with self.as_user(USER_1), installed_apps(APPS_WITH_ERPNEXT):
            workbook_name = create_workbook_from_template(SEED_TEMPLATE)

            # the created workbook remembers its origin
            self.assertEqual(
                frappe.db.get_value("Insights Workbook", workbook_name, "from_template"),
                SEED_TEMPLATE,
            )

            # and the gallery now points the template at that workbook
            seed = {t["name"]: t for t in get_workbook_templates()}[SEED_TEMPLATE]
            self.assertEqual(seed["imported_workbook"], workbook_name)

        # deleting the workbook re-enables the template (state is derived, not stored)
        frappe.delete_doc("Insights Workbook", workbook_name, force=True)
        with self.as_user(USER_1), installed_apps(APPS_WITH_ERPNEXT):
            seed = {t["name"]: t for t in get_workbook_templates()}[SEED_TEMPLATE]
            self.assertIsNone(seed["imported_workbook"])

    def test_create_blocked_when_required_apps_missing(self):
        with self.as_user(USER_1), installed_apps(APPS_WITHOUT_ERPNEXT):
            with self.assertRaises(frappe.ValidationError):
                create_workbook_from_template(SEED_TEMPLATE)

    def test_create_rejects_unknown_template(self):
        with self.as_user(USER_1):
            with self.assertRaises(frappe.ValidationError):
                create_workbook_from_template("../../../etc/passwd")

    def test_create_workbook_from_template_round_trips_seed(self):
        template = get_template_workbook(SEED_TEMPLATE)

        with self.as_user(USER_1), installed_apps(APPS_WITH_ERPNEXT):
            workbook_name = create_workbook_from_template(SEED_TEMPLATE)
            workbook = get_workbook(workbook_name)

        template_queries = template["dependencies"]["queries"]
        template_charts = template["dependencies"]["charts"]
        template_dashboards = template["dependencies"]["dashboards"]

        self.assertEqual(workbook["title"], template["doc"]["title"])
        self.assertEqual(
            {q["title"] for q in workbook["queries"]},
            {q["title"] for q in template_queries.values()},
        )
        self.assertEqual(
            {c["title"] for c in workbook["charts"]},
            {c["title"] for c in template_charts.values()},
        )
        self.assertEqual(
            {d["title"] for d in workbook["dashboards"]},
            {d["title"] for d in template_dashboards.values()},
        )

        # chart -> query and dashboard -> chart links must be remapped to the new names
        new_query_names = {q["name"] for q in workbook["queries"]}
        new_chart_names = {c["name"] for c in workbook["charts"]}
        for chart in frappe.get_all(
            "Insights Chart v3",
            filters={"workbook": workbook_name},
            fields=["query"],
        ):
            self.assertIn(chart["query"], new_query_names)
        dashboard_name = workbook["dashboards"][0]["name"]
        items = frappe.parse_json(frappe.db.get_value("Insights Dashboard v3", dashboard_name, "items"))
        chart_items = [item for item in items if item["type"] == "chart"]
        self.assertEqual(len(chart_items), len(template_charts))
        for item in chart_items:
            self.assertIn(item["chart"], new_chart_names)

    def test_every_committed_template_is_valid_and_importable(self):
        """CI guard: every committed manifest parses with the required keys and
        every committed workbook.json imports without error."""
        template_names = get_template_names()
        self.assertGreater(len(template_names), 0)

        for name in template_names:
            with self.subTest(template=name):
                manifest = get_template_manifest(name)
                for key in MANIFEST_REQUIRED_KEYS:
                    self.assertIn(key, manifest, f"{name}/manifest.json is missing '{key}'")
                self.assertIsInstance(manifest["required_apps"], list)
                self.assertIsInstance(manifest["source_doctypes"], list)

                workbook_path = os.path.join(get_templates_path(), name, "workbook.json")
                self.assertTrue(os.path.isfile(workbook_path), f"{name} has no workbook.json")
                with open(workbook_path) as f:
                    workbook = json.load(f)
                self.assertTrue(workbook.get("doc", {}).get("title"), f"{name}/workbook.json has no title")

                imported_name = import_workbook(workbook)
                self.assertTrue(frappe.db.exists("Insights Workbook", imported_name))
                frappe.delete_doc("Insights Workbook", imported_name, force=True)
