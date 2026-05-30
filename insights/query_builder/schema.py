import ibis
from ibis.expr.datatypes import DataType


def get_columns_from_schema(schema: ibis.Schema):
    return [
        {
            "name": col,
            "type": to_insights_type(dtype),
        }
        for col, dtype in schema.items()
    ]


def to_insights_type(dtype: DataType):
    if dtype.is_string():
        return "String"
    if dtype.is_integer():
        return "Integer"
    if dtype.is_floating():
        return "Decimal"
    if dtype.is_decimal():
        return "Decimal"
    if dtype.is_timestamp():
        return "Datetime"
    if dtype.is_date():
        return "Date"
    if dtype.is_time():
        return "Time"
    if dtype.is_json():
        return "JSON"
    if dtype.is_array():
        return "Array"
    return "String"
