"""声明式数据范围表达式解析器。

语法（AST 白名单实现，全程不使用 eval / exec）：

    expr      := or_expr
    or_expr   := and_expr ( '|' and_expr )*
    and_expr  := cmp ( ('and'|'&') cmp )*
    cmp       := atom [ OP atom ]
    atom      := '(' expr ')' | KEYWORD | IDENT | NUMBER | STRING
    KEYWORD   := SELF | DEPT | DEPT_TREE | ALL | MY_CREATED | OWN_DEPT
    OP        := '=' | '==' | '!=' | '<>' | '<' | '<=' | '>' | '>='

示例：
    SELF | DEPT
    DEPT_TREE and amount < 5000
    status = OWN_DEPT and created_by != SELF
"""
import re

from django.db.models import Q

KEYWORDS = {"SELF", "DEPT", "DEPT_TREE", "ALL", "MY_CREATED", "OWN_DEPT"}
_OPS = {"=": "", "==": "", "!=": "", "<>": "", "<": "lt", "<=": "lte", ">": "gt", ">=": "gte"}
_TOKEN_RE = re.compile(r"\s*(?:(?P<op><=|>=|!=|<>|<|>|=|==|and|AND|&|\|)|(?P<par>[()])|(?P<str>'[^']*'|\"[^\"]*\")|(?P<word>[A-Za-z_][A-Za-z0-9_.]*)|(?P<num>-?\d+(?:\.\d+)?))")


class ExprError(ValueError):
    pass


class Node:
    def explain(self) -> str:  # pragma: no cover - 抽象
        raise NotImplementedError


class ScopeNode(Node):
    def __init__(self, keyword: str):
        self.keyword = keyword

    def explain(self) -> str:
        return self.keyword


class CmpNode(Node):
    def __init__(self, left: str, op: str, right):
        self.left, self.op, self.right = left, op, right

    def explain(self) -> str:
        right = self.right if isinstance(self.right, str) else str(self.right)
        return f"{self.left} {self.op} {right}"


class AndNode(Node):
    def __init__(self, children):
        self.children = children

    def explain(self) -> str:
        return " and ".join(c.explain() for c in self.children)


class OrNode(Node):
    def __init__(self, children):
        self.children = children

    def explain(self) -> str:
        return " | ".join(c.explain() for c in self.children)


def tokenize(text: str):
    pos, tokens = 0, []
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if not m:
            if text[pos:].strip() == "":
                break
            raise ExprError(f"无法识别的字符：{text[pos:pos+8]}")
        pos = m.end()
        for kind in ("op", "par", "str", "word", "num"):
            v = m.group(kind)
            if v is not None:
                tokens.append((kind, v))
                break
    return tokens


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.i = 0

    def peek(self):
        return self.tokens[self.i] if self.i < len(self.tokens) else (None, None)

    def next(self):
        tok = self.peek()
        self.i += 1
        return tok

    def parse(self) -> Node:
        node = self.parse_or()
        if self.i != len(self.tokens):
            raise ExprError(f"表达式尾部有无法解析的内容：{self.tokens[self.i:]}")
        return node

    def parse_or(self) -> Node:
        children = [self.parse_and()]
        while self.peek()[1] in ("|", "or", "OR"):
            self.next()
            children.append(self.parse_and())
        return children[0] if len(children) == 1 else OrNode(children)

    def parse_and(self) -> Node:
        children = [self.parse_cmp()]
        while self.peek()[1] in ("and", "AND", "&"):
            self.next()
            children.append(self.parse_cmp())
        return children[0] if len(children) == 1 else AndNode(children)

    def parse_cmp(self) -> Node:
        kind, value = self.next()
        if kind is None:
            raise ExprError("表达式意外结束")
        left = self.parse_atom(kind, value)
        if isinstance(left, Node):
            return left
        nk, nv = self.peek()
        if nk == "op" and nv in _OPS:
            self.next()
            rk, rv = self.next()
            if rk is None:
                raise ExprError(f"比较运算符 {nv} 缺少右值")
            right = self.literal(rk, rv)
            return CmpNode(left, nv, right)
        # 裸关键字/标识符（无比较）视为布尔真值条件
        if left in KEYWORDS:
            return ScopeNode(left)
        raise ExprError(f"缺少比较运算符：{left}")

    def parse_atom(self, kind, value):
        if kind == "par" and value == "(":
            node = self.parse_or()
            if self.peek() != ("par", ")"):
                raise ExprError("括号未闭合")
            self.next()
            return node
        if kind == "word" or kind == "num" or kind == "str":
            return self.literal(kind, value)
        raise ExprError(f"意外的记号：{value}")

    def literal(self, kind, value):
        if kind == "str":
            return value[1:-1]
        if kind == "num":
            return float(value) if "." in value else int(value)
        return value


def parse_expr(text: str) -> Node:
    text = (text or "").strip()
    if not text:
        raise ExprError("表达式为空")
    if len(text) > 512:
        raise ExprError("表达式过长")
    return Parser(tokenize(text)).parse()


# ------------------------------------------------------------------ 求值
def _lookup_to_q(field: str, lookup: str, value) -> Q:
    key = field if not lookup else f"{field}__{lookup}"
    return Q(**{key: value})


def resolve_node(node: Node, user, user_field: str = "created_by") -> Q:
    """把 AST 解析为 ORM Q 对象。"""
    if isinstance(node, ScopeNode):
        return resolve_scope(node.keyword, user, user_field)
    if isinstance(node, AndNode):
        q = Q()
        for c in node.children:
            q &= resolve_node(c, user, user_field)
        return q
    if isinstance(node, OrNode):
        q = Q()
        for c in node.children:
            q |= resolve_node(c, user, user_field)
        return q
    if isinstance(node, CmpNode):
        right = resolve_value(node.right, user)
        lookup = _OPS[node.op]
        if node.op in ("!=", "<>"):
            return ~_lookup_to_q(node.left, "", right)
        return _lookup_to_q(node.left, lookup, right)
    raise ExprError(f"无法求值的节点：{node!r}")


def resolve_value(value, user):
    """关键字右值解析。"""
    if not isinstance(value, str) or value not in KEYWORDS:
        return value
    dept = getattr(user, "dept", None)
    if value == "SELF":
        return user.id
    if value == "DEPT":
        return dept.id if dept else -1
    if value == "OWN_DEPT":
        return dept.descendant_ids() if dept else [-1]
    if value == "DEPT_TREE":
        return dept.descendant_ids() if dept else [-1]
    if value == "ALL":
        return None
    if value == "MY_CREATED":
        return user.id
    return value


def resolve_scope(keyword: str, user, user_field: str = "created_by") -> Q:
    dept = getattr(user, "dept", None)
    if keyword == "ALL":
        return Q()
    if keyword == "SELF":
        return Q(**{user_field: user})
    if keyword == "MY_CREATED":
        return Q(created_by=user)
    if keyword == "DEPT":
        return Q(**{f"{user_field}__dept_id": dept.id}) if dept else Q(pk__in=[])
    if keyword == "DEPT_TREE":
        return Q(**{f"{user_field}__dept_id__in": dept.descendant_ids()}) if dept else Q(pk__in=[])
    if keyword == "OWN_DEPT":
        return Q(**{f"{user_field}__dept_id__in": dept.descendant_ids()}) if dept else Q(pk__in=[])
    raise ExprError(f"未知关键字：{keyword}")


def validate_expr(text: str) -> tuple:
    """校验表达式合法性，返回 (ok, message)。"""
    try:
        node = parse_expr(text)
        _assert_fields(node)
        return True, node.explain()
    except ExprError as exc:
        return False, str(exc)


_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _assert_fields(node: Node) -> None:
    """字段名白名单校验：只允许字母数字下划线，防止注入。"""
    if isinstance(node, CmpNode):
        if not _IDENT_RE.match(node.left):
            raise ExprError(f"非法字段名：{node.left}")
        if isinstance(node.right, str) and node.right not in KEYWORDS and not _IDENT_RE.match(node.right):
            if len(node.right) > 64:
                raise ExprError("右值过长")
    for child in getattr(node, "children", []):
        _assert_fields(child)
