import frappe
import ibis
from ibis import _

from insights.insights.query_builders.sql_functions import handle_timespan
from insights.query_builder.columns import (
    get_column,
    get_columns_from_expression,
    rename_duplicate_columns,
    sanitize_name,
)
from insights.query_builder.expressions import (
    evaluate_expression,
    get_ibis_dtype,
    is_date_type,
    translate_dimension,
    translate_measure,
)
from insights.query_builder.script import apply_code
from insights.query_builder.sql import apply_sql


def apply_source(builder, source_args):
    return builder.get_table_or_query(source_args.table)


def apply_join(builder, join_args):
    right_table = get_right_table(builder, join_args)
    join_condition = translate_join_condition(builder, join_args, right_table)
    join_type = "outer" if join_args.join_type == "full" else join_args.join_type
    right_table = rename_duplicate_columns(builder, right_table)
    return builder.query.join(
        right_table,
        join_condition,
        how=join_type,
    )


def get_right_table(builder, join_args):
    right_table = builder.get_table_or_query(join_args.table)

    if not join_args.select_columns:
        return right_table

    select_columns = set()

    for col in join_args.select_columns:
        select_columns.add(col.column_name)

    if join_args.join_condition and join_args.join_condition.right_column:
        select_columns.add(join_args.join_condition.right_column.column_name)

    if join_args.join_condition and join_args.join_condition.join_expression:
        expression = evaluate_expression(
            builder,
            join_args.join_condition.join_expression.expression,
            additonal_context={
                "t1": builder.query,
                "t2": right_table,
            },
        )
        columns_from_exp = get_columns_from_expression(expression)
        if columns_from_exp:
            columns_from_exp = [col for col in columns_from_exp if col in right_table.columns]
            select_columns.update(columns_from_exp)

    return right_table.select(select_columns)


def translate_join_condition(builder, join_args, right_table):
    def left_eq_right_condition(left_column, right_column):
        if left_column and right_column and left_column.column_name and right_column.column_name:
            rt = right_table
            lc = get_column(builder, left_column.column_name)
            rc = rt[right_column.column_name]
            return lc.cast(rc.type()) == rc

        frappe.throw("Join condition is not valid")

    join_condition = join_args.join_condition
    if join_condition.join_expression and join_condition.join_expression.expression:
        return evaluate_expression(
            builder,
            join_condition.join_expression.expression,
            {
                "t1": _,
                "t2": right_table,
            },
        )
    else:
        return left_eq_right_condition(
            join_condition.left_column,
            join_condition.right_column,
        )


def apply_union(builder, union_args):
    other_table = builder.get_table_or_query(union_args.table)

    current_columns = set(builder.query.columns)
    other_columns = set(other_table.columns)
    common_columns = current_columns.intersection(other_columns)

    if not common_columns:
        frappe.throw(
            "Both tables must have at least one common column to perform union",
            title="Cannot Perform Union",
        )

    for col in common_columns:
        left_col_type = builder.query.schema()[col]
        right_col_type = other_table.schema()[col]
        if left_col_type != right_col_type:
            other_table = other_table.cast({col: left_col_type})

    builder.query = builder.query.select(common_columns)
    other_table = other_table.select(common_columns)
    return builder.query.union(other_table, distinct=union_args.distinct)


def apply_filter(builder, filter_args):
    condition = make_filter_condition(builder, filter_args)
    return builder.query.filter(condition)


def make_filter_condition(builder, filter_args):
    if hasattr(filter_args, "expression") and filter_args.expression:
        return evaluate_expression(builder, filter_args.expression.expression)

    filter_column = filter_args.column
    filter_operator = filter_args.operator
    filter_value = filter_args.value

    left = get_column(builder, filter_column.column_name)
    operator_fn = get_operator(filter_operator)

    if operator_fn is None:
        frappe.throw(f"Operator {filter_operator} is not supported")

    right_column = (
        get_column(builder, filter_value.column_name)
        if getattr(filter_value, "column_name", None) is not None
        else None
    )

    if filter_operator in ["contains", "not_contains"]:
        filter_value = filter_value.replace("%", "")

        if left.type().is_numeric():
            left = left.cast("string")

    if filter_operator == "between":
        start = filter_value[0]
        end = filter_value[1]

        if isinstance(start, str) and isinstance(end, str):
            contains_time = ":" in start or ":" in end
            if not contains_time:
                start = f"{start} 00:00:00"
                end = f"{end} 23:59:59"

        filter_value = [start, end]

    right_value = right_column if right_column is not None else filter_value
    return operator_fn(left, right_value)


def get_operator(operator):
    def null_check(is_null, x):
        if is_null:
            rt = x.isnull()
            if x.type().is_string():
                rt = rt | (x == "")
        else:
            rt = x.notnull()
            if x.type().is_string():
                rt = rt & (x != "")
        return rt

    return {
        ">": lambda x, y: x > y,
        "<": lambda x, y: x < y,
        "=": lambda x, y: x == y,
        "!=": lambda x, y: x != y,
        ">=": lambda x, y: x >= y,
        "<=": lambda x, y: x <= y,
        "in": lambda x, y: x.isin(y),
        "not_in": lambda x, y: ~x.isin(y),
        "is_set": lambda x, y: null_check(False, x),
        "is_not_set": lambda x, y: null_check(True, x),
        "contains": lambda x, y: x.like(f"%{y}%"),
        "not_contains": lambda x, y: ~x.like(f"%{y}%"),
        "starts_with": lambda x, y: x.like(f"{y}%"),
        "ends_with": lambda x, y: x.like(f"%{y}"),
        "between": lambda x, y: x.between(y[0], y[1]),
        "within": lambda x, y: handle_timespan(x, y),
    }[operator]


def apply_filter_group(builder, filter_group_args):
    filters = filter_group_args.filters
    if not filters:
        return builder.query

    logical_operator = filter_group_args.logical_operator
    conditions = [make_filter_condition(builder, filter) for filter in filters]

    if logical_operator == "And":
        return builder.query.filter(ibis.and_(*conditions))
    elif logical_operator == "Or":
        return builder.query.filter(ibis.or_(*conditions))

    frappe.throw(f"Logical operator {logical_operator} is not supported")


def apply_select(builder, select_args):
    resolved_names = [get_column(builder, col).get_name() for col in select_args.column_names]
    return builder.query.select(resolved_names)


def apply_rename(builder, rename_args):
    old_name = get_column(builder, rename_args.column.column_name).get_name()
    new_name = sanitize_name(rename_args.new_name)
    return builder.query.rename(**{new_name: old_name})


def apply_remove(builder, remove_args):
    valid_columns = []
    for column_name in remove_args.column_names:
        column = get_column(builder, column_name, throw=False)
        if column is not None:
            valid_columns.append(column.get_name())

    if not valid_columns:
        return builder.query

    return builder.query.drop(*valid_columns)


def apply_cast(builder, cast_args):
    col_name = get_column(builder, cast_args.column.column_name).get_name()
    dtype = get_ibis_dtype(cast_args.data_type)
    return builder.query.cast({col_name: dtype})


def apply_mutate(builder, mutate_args):
    new_name = sanitize_name(mutate_args.new_name)
    new_column = evaluate_expression(builder, mutate_args.expression.expression)
    dtype = get_ibis_dtype(mutate_args.data_type)
    if dtype:
        new_column = new_column.cast(dtype)
    return builder.query.mutate(**{new_name: new_column})


def apply_summary(builder, summarize_args):
    aggregates = [translate_measure(builder, measure) for measure in summarize_args.measures]
    aggregates = {agg.get_name(): agg for agg in aggregates}
    group_bys = [translate_dimension(builder, dimension) for dimension in summarize_args.dimensions]
    return builder.query.aggregate(**aggregates, by=group_bys)


def apply_order_by(builder, order_by_args):
    order_by_column = get_column(builder, order_by_args.column.column_name, throw=False)
    if order_by_column is None:
        return builder.query
    order_fn = ibis.asc if order_by_args.direction == "asc" else ibis.desc
    return builder.query.order_by(order_fn(order_by_column))


def apply_limit(builder, limit_args):
    limit = clamp(limit_args.limit, 1, 10_00_000)
    return builder.query.limit(limit)


def apply_pivot(builder, pivot_args, pivot_type):
    rows = [translate_dimension(builder, dimension) for dimension in pivot_args["rows"]]
    columns = [translate_dimension(builder, dimension) for dimension in pivot_args["columns"]]
    values = [translate_measure(builder, measure) for measure in pivot_args["values"]]

    if pivot_type == "wider":
        builder.query = builder.query.group_by(*rows, *columns).aggregate(
            **{value.get_name(): value for value in values}
        )

        date_dimensions = [
            translate_dimension(builder, dim).get_name()
            for dim in pivot_args["columns"]
            if is_date_type(dim.data_type)
        ]
        if date_dimensions:
            builder.query = builder.query.cast({dimension: "string" for dimension in date_dimensions})

        names_from = [col.get_name() for col in columns]
        max_names = pivot_args.get("max_column_values", 10)
        max_names = int(max_names)
        max_names = max(1, min(max_names, 100))
        names = builder.query.select(names_from).order_by(names_from).distinct().limit(max_names).execute()
        names = names.fillna("null").values

        if len(names) == max_names and len(columns) == 1:
            selected_names = [str(v) for v in names.flatten()]

            col_name = columns[0].get_name()
            col_expr = getattr(builder.query, col_name)

            others_expr = ibis.cases((col_expr.isin(selected_names), col_expr), else_="Others")
            builder.query = builder.query.mutate(**{col_name: others_expr})

            names = list(map(str, selected_names))
            names.append("Others")

        return builder.query.pivot_wider(
            id_cols=[row.get_name() for row in rows],
            names_from=names_from,
            names_sep="___",
            names=names,
            values_from=[value.get_name() for value in values],
            values_agg="sum",
        )

    return builder.query


def apply_pivot_wider(builder, pivot_args):
    return apply_pivot(builder, pivot_args, "wider")


def apply_custom_operation(builder, operation):
    return evaluate_expression(builder, operation.expression.expression)


def clamp(value, lo: int, hi: int) -> int:
    try:
        return max(lo, min(int(value), hi))
    except (TypeError, ValueError):
        return lo


OPERATORS = {
    "source": apply_source,
    "join": apply_join,
    "union": apply_union,
    "filter": apply_filter,
    "filter_group": apply_filter_group,
    "select": apply_select,
    "rename": apply_rename,
    "remove": apply_remove,
    "mutate": apply_mutate,
    "cast": apply_cast,
    "summarize": apply_summary,
    "pivot_wider": apply_pivot_wider,
    "order_by": apply_order_by,
    "limit": apply_limit,
    "custom_operation": apply_custom_operation,
    "sql": apply_sql,
    "code": apply_code,
}
