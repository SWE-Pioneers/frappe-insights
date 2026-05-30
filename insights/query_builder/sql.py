import re
from datetime import date

import frappe
import ibis
import pandas as pd
import sqlglot as sg
import sqlparse

import insights
from insights.insights.doctype.insights_table_v3.insights_table_v3 import InsightsTablev3


def extract_sql_table_refs(raw_sql: str, dialect: sg.Dialect | None = None) -> list[frappe._dict]:
    try:
        parsed = sg.parse_one(raw_sql, dialect=dialect)
    except Exception:
        return []

    cte_aliases = {
        str(alias)
        for cte_exp in parsed.find_all(sg.exp.CTE)
        if (alias := getattr(cte_exp, "alias_or_name", None) or cte_exp.alias)
    }

    table_refs = []
    seen_refs = set()
    for table_exp in parsed.find_all(sg.exp.Table):
        table_name = table_exp.name
        if not table_name or table_name in cte_aliases:
            continue

        table_ref = frappe._dict(
            name=table_name,
            db=str(table_exp.db) if table_exp.db else None,
            catalog=str(table_exp.catalog) if table_exp.catalog else None,
        )
        ref_key = (table_ref.name, table_ref.db, table_ref.catalog)
        if ref_key in seen_refs:
            continue

        seen_refs.add(ref_key)
        table_refs.append(table_ref)

    return table_refs


def apply_sql(builder, sql_args):
    data_source = sql_args.data_source
    raw_sql = sql_args.raw_sql

    ds = frappe.get_doc("Insights Data Source v3", data_source)
    db = ds._get_ibis_backend() if builder.use_live_connection else insights.warehouse.db
    source_dialect = ds.get_sqlglot_dialect()

    raw_sql = sqlparse.format(sql=raw_sql, strip_comments=True)
    raw_sql = validate_native_sql(raw_sql, use_live_connection=builder.use_live_connection)

    check_permissions = any(
        frappe.get_single_value("Insights Settings", ["enable_permissions", "apply_user_permissions"])
    )

    if check_permissions or not builder.use_live_connection:
        tables = get_sql_table_names(
            raw_sql,
            dialect=source_dialect,
            use_live_connection=builder.use_live_connection,
        )
        replace_map = get_sql_table_bindings(
            data_source,
            tables,
            dialect=source_dialect,
            use_live_connection=builder.use_live_connection,
            check_permissions=check_permissions,
        )

        if not builder.use_live_connection:
            raw_sql = transpile_sql_to_duckdb(raw_sql, source_dialect)

        raw_sql = prepend_sql_with_clauses(raw_sql, replace_map)

    supports_stored_procedure = ds.database_type in ["PostgreSQL", "MSSQL", "MariaDB"]
    if (
        supports_stored_procedure
        and ds.enable_stored_procedure_execution
        and raw_sql.strip().lower().startswith("exec")
    ):
        current_date = date.today().strftime("%Y-%m-%d")
        raw_sql = raw_sql.replace("@Today", f"'{current_date}'")

        result = db.raw_sql(raw_sql)

        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()

        df = pd.DataFrame.from_records(rows, columns=columns)

        results = ibis.memtable(df)

    elif raw_sql.strip().lower().startswith(("select", "with")):
        results = db.sql(raw_sql)

    else:
        frappe.throw(
            "SQL query must start with a SELECT or WITH statement",
            title="Invalid SQL Query",
        )

    return results


def validate_native_sql(raw_sql: str, use_live_connection: bool) -> str:
    raw_sql = raw_sql.strip()

    if not use_live_connection:
        statements = [stmt for stmt in sqlparse.parse(raw_sql) if stmt.tokens and stmt.value.strip()]
        if len(statements) > 1:
            frappe.throw(
                "Multiple SQL statements are not supported with Data Store for native queries",
                title="Unsupported SQL Query",
            )

        if raw_sql.lower().startswith("exec"):
            frappe.throw(
                "Stored procedures are not supported with Data Store for native queries",
                title="Unsupported SQL Query",
            )

    return raw_sql


def transpile_sql_to_duckdb(raw_sql: str, source_dialect: str | None) -> str:
    if not source_dialect or source_dialect == "duckdb":
        return raw_sql

    try:
        transpiled_sql = sg.transpile(raw_sql, read=source_dialect, write="duckdb")
    except Exception as e:
        frappe.throw(
            f"Failed to translate SQL query for Data Store execution: {e}",
            title="Unsupported SQL Query",
        )

    if not transpiled_sql:
        frappe.throw(
            "Failed to translate SQL query for Data Store execution",
            title="Unsupported SQL Query",
        )

    return transpiled_sql[0]


def get_sql_table_names(raw_sql: str, dialect: sg.Dialect | None, use_live_connection: bool) -> set[str]:
    tables = set()
    for table_ref in extract_sql_table_refs(raw_sql, dialect=dialect):
        if not use_live_connection and (table_ref.db or table_ref.catalog):
            frappe.throw(
                "Schema-qualified table names are not supported with Data Store for native queries yet",
                title="Unsupported SQL Query",
            )

        tables.add(table_ref.name)

    return tables


def get_sql_table_bindings(
    data_source: str,
    tables: set[str],
    dialect: sg.Dialect | None,
    use_live_connection: bool,
    check_permissions: bool,
) -> dict[str, str]:
    replace_map = {}

    for table_name in tables:
        table_expr = InsightsTablev3.get_ibis_table(
            data_source,
            table_name,
            use_live_connection=use_live_connection,
        )
        table_sql = ibis.to_sql(table_expr)

        if use_live_connection and check_permissions:
            table_sql_parsed = sg.parse_one(table_sql, dialect=dialect)
            if not table_sql_parsed.find(sg.exp.Where):
                continue

        replace_map[table_name] = table_sql

    return replace_map


def prepend_sql_with_clauses(raw_sql: str, replace_map: dict[str, str]) -> str:
    if not replace_map:
        return raw_sql

    with_clauses = []
    for table_name, table_sql in replace_map.items():
        quoted_table_name = sg.to_identifier(table_name)
        with_clauses.append(f"{quoted_table_name} AS ({table_sql})")

    with_clause_sql = ", ".join(with_clauses)
    raw_sql_stripped = raw_sql.strip()
    if raw_sql_stripped.lower().startswith("with"):
        return re.sub(
            r"(\bwith\b)",
            f"WITH {with_clause_sql},",
            raw_sql_stripped,
            count=1,
            flags=re.IGNORECASE,
        )

    return f"WITH {with_clause_sql} {raw_sql_stripped}"
