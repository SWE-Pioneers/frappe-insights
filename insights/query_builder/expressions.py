import frappe
from ibis.expr.operations.relations import DatabaseTable

from insights.insights.doctype.insights_data_source_v3.ibis.functions import fiscal_year_start, week_start
from insights.insights.doctype.insights_data_source_v3.ibis.utils import get_functions
from insights.query_builder.columns import get_column
from insights.query_builder.script import SafePandasDataFrame, exec_with_return


def evaluate_expression(builder, expression, additonal_context=None):
    if not expression or not expression.strip():
        raise ValueError(f"Invalid expression: {expression}")

    frappe.flags.current_ibis_query = builder.query
    context = frappe._dict()
    context.pandas = frappe._dict()
    context.pandas.DataFrame = SafePandasDataFrame
    context.q = builder.query
    context.update(get_current_columns(builder))
    context.update(get_functions())
    context.update(additonal_context or {})
    ret = exec_with_return(expression, context)
    frappe.flags.current_ibis_query = None
    return ret


def get_current_columns(builder):
    return {col: getattr(builder.query, col) for col in builder.query.schema().names}


def translate_measure(builder, measure):
    if measure.column_name == "count" and measure.aggregation == "count":
        first_column = builder.query.columns[0]
        first_column = getattr(builder.query, first_column)
        return first_column.count().name(measure.measure_name)

    if "expression" in measure:
        column = evaluate_expression(builder, measure.expression.expression)
        dtype = get_ibis_dtype(measure.data_type)
        column = column.cast(dtype)
    else:
        column = get_column(builder, measure.column_name)
        column = apply_aggregate(column, measure.aggregation)

    return column.name(measure.measure_name)


def translate_dimension(builder, dimension):
    col = get_column(builder, dimension.column_name)
    if is_date_type(dimension.data_type) and dimension.granularity:
        col = apply_granularity(col, dimension.granularity)
        col = col.cast(get_ibis_dtype(dimension.data_type))
    return col.name(dimension.dimension_name or dimension.column_name)


def is_date_type(data_type):
    return data_type in ["Date", "Datetime", "Time"]


def apply_aggregate(column, aggregate_function):
    if aggregate_function == "count_distinct":
        return column.nunique()
    if aggregate_function == "count":
        return column.count()
    if aggregate_function == "sum":
        return column.sum()
    if aggregate_function == "avg":
        return column.mean()
    if aggregate_function == "min":
        return column.min()
    if aggregate_function == "max":
        return column.max()

    frappe.throw(f"Aggregate function {aggregate_function} is not supported")


def apply_granularity(column, granularity):
    if granularity == "week":
        return week_start(column).name(column.get_name())
    if granularity == "fiscal_year":
        return fiscal_year_start(column).name(column.get_name())

    truncate_unit = {
        "second": "s",
        "minute": "m",
        "hour": "h",
        "day": "D",
        "quarter": "Q",
        "month": "M",
        "year": "Y",
    }
    if granularity not in truncate_unit:
        frappe.throw(f"Granularity {granularity} is not supported")
    return column.truncate(truncate_unit[granularity]).name(column.get_name())


def get_ibis_dtype(data_type):
    return {
        "String": "string",
        "Integer": "int64",
        "Decimal": "float64",
        "Date": "date",
        "Datetime": "timestamp",
        "Time": "time",
        "Text": "string",
        "JSON": "json",
        "Array": "array<json>",
        "Auto": "",
    }[data_type]


def get_table_names(expression):
    return [dt.name for dt in expression.op().find_topmost(DatabaseTable)]
