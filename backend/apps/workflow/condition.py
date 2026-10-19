"""流程条件分支表达式求值（AST 白名单，禁止 eval）。

支持：days > 3 / amount >= 5000 / urgency == high / category != leave
"""
from apps.accounts.expr import ExprError, parse_expr
from apps.accounts.expr import AndNode, CmpNode, OrNode, ScopeNode

_OPS = {
    "=": lambda a, b: a == b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "<>": lambda a, b: a != b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
}


def _cast(value):
    """把上下文里的值统一成可比较类型。"""
    if isinstance(value, (int, float)):
        return value
    if value is None:
        return 0
    text = str(value)
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def evaluate(node, ctx: dict) -> bool:
    if isinstance(node, ScopeNode):
        # 裸关键字在流程条件中恒为真（如 ALL）
        return node.keyword == "ALL"
    if isinstance(node, AndNode):
        return all(evaluate(c, ctx) for c in node.children)
    if isinstance(node, OrNode):
        return any(evaluate(c, ctx) for c in node.children)
    if isinstance(node, CmpNode):
        left = _cast(ctx.get(node.left))
        right = _cast(node.right)
        try:
            return _OPS[node.op](left, right)
        except TypeError:
            return False
    return False


def check_condition(expr: str, ctx: dict) -> bool:
    """空表达式视为无条件（恒成立）。"""
    if not expr or not expr.strip():
        return True
    try:
        return evaluate(parse_expr(expr), ctx)
    except ExprError:
        return True
