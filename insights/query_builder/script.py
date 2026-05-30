import ast
from contextlib import contextmanager

import frappe
import pandas as pd
from frappe.utils.safe_exec import safe_eval, safe_exec

import insights
from insights.cache_utils import make_digest
from insights.execution import cache_results, get_cached_results


class SafePandasDataFrame(pd.DataFrame):
    def to_csv(self, *args, **kwargs):
        raise NotImplementedError("to_csv is not supported in this context")

    def to_json(self, *args, **kwargs):
        raise NotImplementedError("to_json is not supported in this context")


def apply_code(builder, code_args):
    code = code_args.code

    adhoc_filters = frappe.as_json(getattr(frappe.local, "insights_adhoc_filters", {}))
    digest = make_digest(code + adhoc_filters)

    cached_results = get_cached_results(digest)
    if cached_results is not None:
        results = cached_results
    else:
        variables = None
        if hasattr(builder.doc, "variables") and builder.doc.variables:
            variables = builder.doc.variables
        results = get_code_results(code, variables=variables)
        cache_results(digest, results, cache_expiry=60 * 5)

    return insights.warehouse.db.create_table(
        digest,
        results,
        temp=True,
        overwrite=True,
    )


def exec_with_return(
    script: str,
    _globals: dict | None = None,
    _locals: dict | None = None,
):
    tree = ast.parse(script)

    if not tree.body:
        raise ValueError("Empty code")

    output_expression = script

    last_node = tree.body[-1]
    if isinstance(last_node, ast.Expr):
        output_expression = ast.unparse(last_node)
    elif isinstance(last_node, ast.Assign):
        output_expression = ast.unparse(last_node.value)
    elif isinstance(last_node, ast.AnnAssign | ast.AugAssign):
        output_expression = ast.unparse(last_node.value)

    _globals = _globals or {}
    _locals = _locals or {}

    tree.body.pop()
    _script = ast.unparse(tree)
    if _script.strip():
        with ensure_rollback():
            safe_exec(_script, _globals, _locals, restrict_commit_rollback=True)
        return safe_eval(output_expression, _globals, _locals)
    else:
        return safe_eval(output_expression, _globals, _locals)


def get_code_results(code: str, variables=None):
    pandas = frappe._dict()
    pandas.DataFrame = SafePandasDataFrame
    pandas.read_csv = pd.read_csv
    pandas.json_normalize = pd.json_normalize

    results = []
    frappe.local.debug_log = []

    variable_context = {}
    if variables:
        from frappe.utils.password import get_decrypted_password

        for var in variables:
            if hasattr(var, "variable_name") and hasattr(var, "variable_value"):
                variable_context[var.variable_name] = get_decrypted_password(
                    var.doctype, var.name, "variable_value"
                )
            elif isinstance(var, dict):
                variable_context[var.get("variable_name")] = var.get("variable_value")

    _locals = {"results": results, **variable_context}
    with ensure_rollback():
        _, _locals = safe_exec(
            code,
            _globals={"pandas": pandas},
            _locals=_locals,
            restrict_commit_rollback=True,
        )

    results = _locals["results"]
    if results is None or len(results) == 0:
        results = [{"error": "No results"}]

    frappe.publish_realtime(
        event="insights_script_log",
        user=frappe.session.user,
        message={
            "user": frappe.session.user,
            "logs": frappe.debug_log,
        },
    )

    if not isinstance(results, pd.DataFrame):
        results = pd.DataFrame(results)

    return results


@contextmanager
def ensure_rollback():
    hash = frappe.generate_hash(length=4)
    try:
        frappe.db.savepoint(f"save_point_{hash}")
        yield
    finally:
        frappe.db.rollback(save_point=f"save_point_{hash}")
