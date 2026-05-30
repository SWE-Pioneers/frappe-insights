import time

import frappe
import ibis
import numpy as np
import pandas as pd
from frappe.utils.data import flt
from ibis.expr.types import Table as IbisQuery

from insights.cache_utils import make_digest
from insights.insights.doctype.insights_data_source_v3.data_warehouse import is_warehouse
from insights.utils import create_execution_log

try:
    from frappe.concurrency_limiter import concurrent_limit
except ImportError:

    def concurrent_limit(limit=None, wait_timeout=None):
        def decorator(func):
            return func

        return decorator


def clamp(value, lo: int, hi: int) -> int:
    try:
        return max(lo, min(int(value), hi))
    except (TypeError, ValueError):
        return lo


def execute_ibis_query(
    query: IbisQuery,
    page=1,
    page_size=100,
    paginate=True,
    force=False,
    cache=True,
    cache_expiry=3600,
    reference_doctype=None,
    reference_name=None,
):
    if paginate and hasattr(query, "limit"):
        page_size = clamp(page_size, 1, 10_000)
        page = clamp(page, 1, 10_000)
        offset = (page - 1) * page_size
        query = query.limit(page_size, offset=offset)

    try:
        sql = ibis.to_sql(query)
    except ibis.common.exceptions.OperationNotDefinedError:
        raise

    backend = query.get_backend()
    if cache:
        backend_id = backend.db_identity if backend else None
        cache_key = make_digest(sql, backend_id)

        if has_cached_results(cache_key) and not force:
            return get_cached_results(cache_key), -1

    time_taken = -1
    use_data_store = is_warehouse(backend)

    try:
        if use_data_store:
            start = time.monotonic()
            result = query.execute()
            time_taken = flt(time.monotonic() - start, 3)
        else:
            result, time_taken = _execute_live_query(query)
    except Exception as e:
        if "max_statement_time" in str(e):
            frappe.log_error(
                title="Query execution time exceeded the limit.",
                message=f"Query: {sql}",
            )
            max_time = frappe.db.get_single_value("Insights Settings", "max_execution_time") or 180
            frappe.throw(
                title="Query Timeout",
                msg=f"Query execution time exceeded the limit of {max_time} seconds. Please try again with a smaller timespan or a more specific filter.",
            )
        raise e

    create_execution_log(
        sql,
        time_taken,
        query_name=reference_name,
        data_store=use_data_store,
    )

    if isinstance(result, pd.DataFrame):
        result = result.replace({pd.NaT: None, np.nan: None})
        if cache:
            cache_results(cache_key, result, cache_expiry)

    return result, time_taken


@concurrent_limit()
def _execute_live_query(query: IbisQuery):
    start = time.monotonic()
    result = query.execute()
    return result, flt(time.monotonic() - start, 3)


def cache_results(cache_key, result: pd.DataFrame, cache_expiry=3600):
    cache_key = "insights:query_results:" + cache_key
    data = result.to_dict(orient="records")
    data = frappe.as_json(data)
    frappe.cache().set_value(cache_key, data, expires_in_sec=cache_expiry)


def get_cached_results(cache_key) -> pd.DataFrame:
    cache_key = "insights:query_results:" + cache_key
    data = frappe.cache().get_value(cache_key)
    if not data:
        return None
    data = frappe.parse_json(data)
    df = pd.DataFrame(data).replace({pd.NaT: None, np.nan: None})
    return df


def has_cached_results(cache_key):
    cache_key = "insights:query_results:" + cache_key
    return frappe.cache().get_value(cache_key) is not None
