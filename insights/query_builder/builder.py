import frappe
from ibis.expr.types import Table as IbisQuery

from insights import create_toast
from insights.insights.doctype.insights_table_v3.insights_table_v3 import InsightsTablev3
from insights.query_builder.cycle import CircularQueryReferenceError, building
from insights.query_builder.operations import OPERATORS
from insights.utils import deep_convert_dict_to_dict as _dict


class IbisQueryBuilder:
    def __init__(self, doc, active_operation_idx=None):
        self.doc = doc
        self.title = self.doc.title or self.doc.name
        self.active_operation_idx = active_operation_idx
        self.use_live_connection = bool(doc.use_live_connection)
        self.operations = doc.operations
        self.set_operations()

    def set_operations(self):
        operations = frappe.parse_json(self.operations)

        if (
            self.active_operation_idx is not None
            and self.active_operation_idx >= 0
            and self.active_operation_idx < len(operations)
        ):
            operations = operations[: self.active_operation_idx + 1]

        self.operations = operations

    def build(self) -> IbisQuery:
        with building(self.doc.name, self.title):
            self.query = None
            for idx, operation in enumerate(self.operations):
                try:
                    operation = _dict(operation)
                    self.query = self.perform_operation(operation)
                except CircularQueryReferenceError:
                    raise
                except BaseException as e:
                    operation_type_title = frappe.bold(operation.type.title())
                    create_toast(
                        title=f"Failed to Build {self.title} Query",
                        message=f"Please check the {operation_type_title} operation at position {idx + 1}",
                        type="error",
                    )
                    raise e
            return self.query

    def perform_operation(self, operation):
        operator = OPERATORS.get(operation.type)
        if operator:
            return operator(self, operation)

        return self.query

    def get_table_or_query(self, table_args):
        _table = None

        if table_args.type == "table":
            _table = InsightsTablev3.get_ibis_table(
                table_args.data_source,
                table_args.table_name,
                use_live_connection=self.use_live_connection,
            )
        if table_args.type == "query":
            q = frappe.get_doc("Insights Query v3", table_args.query_name)
            _table = q.build(use_live_connection=self.use_live_connection)

        if _table is None:
            frappe.throw("Table or Query not found")

        return _table
