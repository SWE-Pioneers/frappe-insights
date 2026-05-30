# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.utils import add_days, nowdate

from insights.insights.doctype.insights_data_source_v3.insights_data_source_v3 import db_connections
from insights.query_builder import IbisQueryBuilder
from insights.tests.base import InsightsIntegrationTestCase
from insights.tests.factories import (
    USER_1,
    cleanup_workbook_flow_fixtures,
    create_test_query,
    create_test_user,
    create_test_workbook,
)

TODO_PREFIX = "Insights Query v3 Builder Test"


def column(column_name):
    return {"type": "column", "column_name": column_name}


def table_source(table_name="tabToDo"):
    return {
        "type": "source",
        "table": {
            "type": "table",
            "data_source": "Site DB",
            "table_name": table_name,
        },
    }


class TestInsightsQueryv3(InsightsIntegrationTestCase):
    COMMIT_AFTER_TEST_SETUP = True
    COMMIT_AFTER_TEST_TEARDOWN = True

    @classmethod
    def before_class(cls):
        cleanup_workbook_flow_fixtures()
        cls.delete_test_todos()
        create_test_user(USER_1)

    @classmethod
    def after_class(cls):
        cls.delete_test_todos()
        cleanup_workbook_flow_fixtures()

    def before_test(self):
        self.delete_test_todos()
        cleanup_workbook_flow_fixtures()
        create_test_user(USER_1)

    def after_test(self):
        self.delete_test_todos()
        cleanup_workbook_flow_fixtures()

    @staticmethod
    def delete_test_todos():
        todo_names = frappe.get_all(
            "ToDo",
            filters={"description": ["like", f"{TODO_PREFIX}%"]},
            pluck="name",
        )
        for todo_name in todo_names:
            frappe.delete_doc("ToDo", todo_name, force=True)

    def seed_todos(self):
        for record in [
            {
                "description": f"{TODO_PREFIX} Open Alpha",
                "status": "Open",
                "date": add_days(nowdate(), 1),
                "allocated_to": USER_1,
            },
            {
                "description": f"{TODO_PREFIX} Closed Beta",
                "status": "Closed",
                "date": add_days(nowdate(), 2),
                "allocated_to": USER_1,
            },
            {
                "description": f"{TODO_PREFIX} Open Gamma",
                "status": "Open",
                "date": add_days(nowdate(), 3),
                "allocated_to": USER_1,
            },
        ]:
            frappe.get_doc({"doctype": "ToDo", **record}).insert(ignore_permissions=True)
        frappe.db.commit()

    def test_builder_uses_operations_up_to_active_operation_idx(self):
        self.seed_todos()
        workbook = create_test_workbook(USER_1)
        query = create_test_query(
            USER_1,
            workbook.name,
            title="Insights Query v3 Builder Active Operation",
            operations=[
                table_source(),
                {
                    "type": "filter",
                    "column": column("status"),
                    "operator": "=",
                    "value": "Open",
                },
                {
                    "type": "mutate",
                    "new_name": "docstatus_plus_one",
                    "expression": {"type": "expression", "expression": "docstatus + 1"},
                    "data_type": "Integer",
                },
            ],
        )

        with db_connections():
            ibis_query = IbisQueryBuilder(query, active_operation_idx=1).build()
            result = ibis_query.order_by("description").execute()

        rows = result.to_dict("records")
        self.assertNotIn("docstatus_plus_one", result.columns)
        self.assertEqual(
            [row["description"] for row in rows if row["description"].startswith(TODO_PREFIX)],
            [
                f"{TODO_PREFIX} Open Alpha",
                f"{TODO_PREFIX} Open Gamma",
            ],
        )

    def test_execute_applies_adhoc_filter_operation_after_builder_operations(self):
        self.seed_todos()
        workbook = create_test_workbook(USER_1)
        query = create_test_query(
            USER_1,
            workbook.name,
            title="Insights Query v3 Builder Adhoc Filter",
            operations=[
                table_source(),
                {
                    "type": "filter",
                    "column": column("description"),
                    "operator": "contains",
                    "value": TODO_PREFIX,
                },
            ],
        )

        with db_connections():
            result = query.execute(
                adhoc_filters={
                    query.name: {
                        "type": "filter_group",
                        "logical_operator": "And",
                        "filters": [
                            {
                                "column": column("status"),
                                "operator": "=",
                                "value": "Closed",
                            }
                        ],
                    }
                }
            )

        self.assertEqual(len(result["rows"]), 1)
        self.assertEqual(result["rows"][0]["description"], f"{TODO_PREFIX} Closed Beta")
