import frappe
from ibis.expr.operations.relations import DatabaseTable, Field
from ibis.expr.types import Expr
from ibis.expr.types import Table as IbisQuery


def get_column(builder, column_name, throw=True):
    if column_name in builder.query.columns:
        return builder.query[column_name]

    if sanitize_name(column_name) in builder.query.columns:
        return builder.query[sanitize_name(column_name)]

    suffix = f"_{column_name}"
    suffix_matches = [col for col in builder.query.columns if col.endswith(suffix)]
    if len(suffix_matches) == 1:
        return builder.query[suffix_matches[0]]

    all_dt = builder.query.op().find_topmost(DatabaseTable)
    schemas = {
        dt.namespace.database
        for dt in all_dt
        if dt.namespace and dt.namespace.database and dt.namespace.database != "main"
    }
    for schema in schemas:
        prefix = f"{schema}_"
        if column_name.startswith(prefix):
            remainder = column_name[len(prefix) :]
            if remainder in builder.query.columns:
                return builder.query[remainder]
            if sanitize_name(remainder) in builder.query.columns:
                return builder.query[sanitize_name(remainder)]

    if throw:
        frappe.throw(f"Column {column_name} does not exist in the table")


def get_columns_from_expression(expression: Expr, table: str | None = None):
    exp_columns = expression.op().find_topmost(Field)
    if not table:
        return list({col.name for col in exp_columns})

    columns = set()
    for col in exp_columns:
        col_table = col.rel.find_topmost(DatabaseTable)[0]
        if col_table and col_table.name == table:
            columns.add(col.name)

    return list(columns)


def rename_duplicate_columns(builder, right_table):
    query: IbisQuery = builder.query
    query_columns = set(query.columns)
    right_table_columns = set(right_table.columns)
    right_table_name = get_ibis_table_name(right_table)
    right_table_name = sanitize_name(right_table_name)

    duplicate_columns = query_columns.intersection(right_table_columns)
    if not duplicate_columns:
        return right_table

    def is_conflicting(col):
        return col in query_columns or col in right_table_columns

    def get_new_name(col):
        new_name = f"{right_table_name}_{col}"
        if not is_conflicting(new_name):
            return new_name

        n = 1
        while is_conflicting(f"{new_name}_{n}"):
            n += 1
            if n > 20:
                frappe.throw("Too many duplicate columns")

        return f"{new_name}_{n}"

    return right_table.rename(**{get_new_name(col): col for col in duplicate_columns})


def get_ibis_table_name(table: IbisQuery):
    dt = table.op().find_topmost(DatabaseTable)
    if not dt:
        return "right_table"
    return dt[0].name


def sanitize_name(name):
    if not name:
        return name
    return (
        name.strip()
        .replace(" ", "_")
        .replace("-", "_")
        .replace(".", "_")
        .replace("/", "_")
        .replace("(", "_")
        .replace(")", "_")
        .lower()
    )
