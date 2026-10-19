"""初始化基础数据：权限点、角色、菜单树、组织架构、管理员账号。

幂等：重复执行不会产生重复数据。
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import (
    Department,
    Menu,
    Permission,
    Position,
    Role,
    RolePermission,
    SystemParam,
    User,
    UserRole,
)

# ---------------------------------------------------------------- 权限点清单
PERMISSIONS = [
    # module, code, name, kind
    ("accounts", "accounts:user:list", "用户列表", "api"),
    ("accounts", "accounts:user:create", "新建用户", "button"),
    ("accounts", "accounts:user:update", "修改用户", "button"),
    ("accounts", "accounts:user:destroy", "删除用户", "button"),
    ("accounts", "accounts:user:assign_roles", "分配角色", "button"),
    ("accounts", "accounts:dept:list", "部门列表", "api"),
    ("accounts", "accounts:dept:create", "新建部门", "button"),
    ("accounts", "accounts:dept:update", "修改部门", "button"),
    ("accounts", "accounts:dept:destroy", "删除部门", "button"),
    ("accounts", "accounts:position:list", "岗位列表", "api"),
    ("accounts", "accounts:position:create", "新建岗位", "button"),
    ("accounts", "accounts:position:update", "修改岗位", "button"),
    ("accounts", "accounts:position:destroy", "删除岗位", "button"),
    ("accounts", "accounts:role:list", "角色列表", "api"),
    ("accounts", "accounts:role:create", "新建角色", "button"),
    ("accounts", "accounts:role:update", "修改角色", "button"),
    ("accounts", "accounts:role:destroy", "删除角色", "button"),
    ("accounts", "accounts:permission:list", "权限点列表", "api"),
    ("accounts", "accounts:permission:create", "新建权限点", "button"),
    ("accounts", "accounts:permission:update", "修改权限点", "button"),
    ("accounts", "accounts:permission:destroy", "删除权限点", "button"),
    ("accounts", "accounts:menu:list", "菜单列表", "api"),
    ("accounts", "accounts:menu:create", "新建菜单", "button"),
    ("accounts", "accounts:menu:update", "修改菜单", "button"),
    ("accounts", "accounts:menu:destroy", "删除菜单", "button"),
    ("accounts", "accounts:scope:list", "数据范围规则列表", "api"),
    ("accounts", "accounts:scope:create", "新建数据范围规则", "button"),
    ("accounts", "accounts:scope:update", "修改数据范围规则", "button"),
    ("accounts", "accounts:scope:destroy", "删除数据范围规则", "button"),
    ("accounts", "accounts:sandbox:simulate", "权限沙盘预演", "api"),
    ("accounts", "accounts:sandbox:apply", "权限变更生效", "button"),
    ("accounts", "accounts:sandbox:rollback", "权限变更回滚", "button"),
    ("accounts", "accounts:sandbox:changes", "权限变更记录", "api"),
    ("accounts", "accounts:explain:permission", "权限决策解释", "api"),
    ("accounts", "accounts:explain:data_scope", "数据范围解释", "api"),
    ("accounts", "accounts:oplog:list", "操作日志列表", "api"),
    ("accounts", "accounts:oplog:verify", "日志哈希链校验", "button"),
    ("accounts", "accounts:loginlog:list", "登录日志列表", "api"),
    ("accounts", "accounts:sensitive:apply", "申请查看明文", "button"),
    ("accounts", "accounts:sensitive:grant", "审批明文授权", "button"),
    ("accounts", "accounts:sensitive:view", "查看明文", "button"),
    ("accounts", "accounts:sensitive:logs", "明文访问日志", "api"),
    ("accounts", "accounts:param:list", "系统参数列表", "api"),
    ("accounts", "accounts:param:create", "新建系统参数", "button"),
    ("accounts", "accounts:param:update", "修改系统参数", "button"),
    ("accounts", "accounts:param:destroy", "删除系统参数", "button"),
    ("security", "sensitive:plaintext:view", "敏感字段明文可见", "api"),
    ("security", "sensitive:grant", "敏感字段授权审批", "api"),

    ("workflow", "workflow:template:list", "流程模板列表", "api"),
    ("workflow", "workflow:template:create", "新建流程模板", "button"),
    ("workflow", "workflow:template:update", "修改流程模板", "button"),
    ("workflow", "workflow:template:destroy", "删除流程模板", "button"),
    ("workflow", "workflow:template:publish", "发布流程模板", "button"),
    ("workflow", "workflow:instance:list", "流程实例列表", "api"),
    ("workflow", "workflow:instance:create", "发起申请", "button"),
    ("workflow", "workflow:instance:retrieve", "申请详情", "api"),
    ("workflow", "workflow:instance:approve", "审批操作", "button"),
    ("workflow", "workflow:instance:revoke", "撤回申请", "button"),
    ("workflow", "workflow:instance:urge", "催办", "button"),
    ("workflow", "workflow:task:list", "审批任务列表", "api"),
    ("workflow", "workflow:replay:run", "流程沙盘回放", "api"),
    ("workflow", "workflow:replay:report", "回放报告", "api"),
    ("workflow", "workflow:health:view", "流程健康度", "api"),

    ("attendance", "attendance:punch:create", "打卡", "button"),
    ("attendance", "attendance:record:list", "考勤记录列表", "api"),
    ("attendance", "attendance:record:export", "考勤报表导出", "button"),
    ("attendance", "attendance:rule:list", "考勤规则列表", "api"),
    ("attendance", "attendance:rule:update", "配置考勤规则", "button"),
    ("attendance", "attendance:exception:list", "异常考勤列表", "api"),
    ("attendance", "attendance:exception:handle", "异常考勤处理", "button"),
    ("attendance", "attendance:summary:dept", "部门考勤汇总", "api"),
    ("attendance", "attendance:rule:create", "新建考勤规则", "button"),
    ("attendance", "attendance:rule:destroy", "删除考勤规则", "button"),
    ("attendance", "attendance:punch:list", "打卡记录列表", "api"),
    ("attendance", "attendance:record:rebuild", "重算考勤数据", "button"),
    ("attendance", "attendance:summary:monthly", "个人月度汇总", "api"),

    ("announcement", "announcement:list", "公告列表", "api"),
    ("announcement", "announcement:create", "发布公告", "button"),
    ("announcement", "announcement:update", "编辑公告", "button"),
    ("announcement", "announcement:destroy", "删除公告", "button"),
    ("announcement", "announcement:stats", "阅读统计", "api"),

    ("document", "document:list", "文档列表", "api"),
    ("document", "document:upload", "上传文档", "button"),
    ("document", "document:download", "下载文档", "button"),
    ("document", "document:destroy", "删除文档", "button"),
    ("document", "document:share", "共享设置", "button"),
    ("document", "document:update", "编辑文档信息", "button"),

    ("hr", "hr:staff:list", "员工档案列表", "api"),
    ("hr", "hr:staff:update", "维护员工档案", "button"),
    ("hr", "hr:transfer:list", "入转调离列表", "api"),
    ("hr", "hr:transfer:create", "办理入转调离", "button"),
    ("hr", "hr:contract:list", "合同列表", "api"),
    ("hr", "hr:contract:create", "新增合同", "button"),
    ("hr", "hr:contract:update", "修改合同", "button"),
    ("hr", "hr:contract:destroy", "删除合同", "button"),
    ("hr", "hr:training:list", "培训记录列表", "api"),
    ("hr", "hr:training:create", "新增培训记录", "button"),
    ("hr", "hr:training:update", "修改培训记录", "button"),
    ("hr", "hr:training:destroy", "删除培训记录", "button"),
    ("hr", "hr:analytics:view", "员工结构分析", "api"),

    ("expense", "expense:apply", "报销申请", "button"),
    ("expense", "expense:list", "报销列表", "api"),
    ("expense", "expense:audit", "报销审核", "button"),
    ("expense", "expense:pay", "支付确认", "button"),
    ("expense", "expense:stats", "报销统计", "api"),

    ("meeting", "meeting:room:list", "会议室列表", "api"),
    ("meeting", "meeting:room:update", "维护会议室", "button"),
    ("meeting", "meeting:booking:create", "预约会议", "button"),
    ("meeting", "meeting:booking:list", "预约列表", "api"),
    ("meeting", "meeting:minute:upload", "上传纪要", "button"),
    ("meeting", "meeting:minute:list", "纪要列表", "api"),
    ("meeting", "meeting:room:create", "新增会议室", "button"),
    ("meeting", "meeting:room:destroy", "删除会议室", "button"),
    ("meeting", "meeting:booking:cancel", "取消预约", "button"),

    ("schedule", "schedule:list", "日程列表", "api"),
    ("schedule", "schedule:create", "新建日程", "button"),
    ("schedule", "schedule:update", "修改日程", "button"),
    ("schedule", "schedule:destroy", "删除日程", "button"),
    ("schedule", "task:list", "任务列表", "api"),
    ("schedule", "task:create", "新建任务", "button"),
    ("schedule", "task:update", "更新任务", "button"),
    ("schedule", "task:destroy", "删除任务", "button"),

    ("message", "message:list", "消息中心", "api"),
    ("message", "message:read", "标记已读", "button"),

    ("insight", "insight:sla:view", "审批时效预测", "api"),
    ("insight", "insight:risk:view", "超时风险看板", "api"),
    ("insight", "insight:bottleneck:view", "瓶颈分析", "api"),

    ("lowcode", "lowcode:form:list", "动态表单列表", "api"),
    ("lowcode", "lowcode:form:create", "新建动态表单", "button"),
    ("lowcode", "lowcode:form:update", "编辑动态表单", "button"),
    ("lowcode", "lowcode:form:destroy", "删除动态表单", "button"),

    ("system", "system:backup:run", "数据备份", "button"),
    ("system", "system:dict:list", "数据字典", "api"),
    ("system", "system:dict:update", "维护数据字典", "button"),
]

# ---------------------------------------------------------------- 菜单树
# (code, name, path, component, icon, type, permission_code, [children])
MENUS = [
    ("dashboard", "工作台", "/dashboard", "Layout", "Odometer", "dir", "", [
        ("dashboard.index", "工作台首页", "index", "dashboard/index", "Odometer", "menu", "", []),
    ]),
    ("workspace", "待办中心", "/workspace", "Layout", "Tickets", "dir", "", [
        ("workspace.todo", "待办中心", "todo", "workspace/todo", "Tickets", "menu", "workflow:task:list", []),
        ("workspace.done", "已办中心", "done", "workspace/done", "CircleCheck", "menu", "workflow:task:list", []),
        ("workspace.mine", "我的申请", "mine", "workspace/mine", "Document", "menu", "workflow:instance:list", []),
    ]),
    ("approval", "流程审批", "/approval", "Layout", "Promotion", "dir", "", [
        ("approval.create", "发起申请", "create", "approval/create", "EditPen", "menu", "workflow:instance:create", []),
        ("approval.list", "申请列表", "list", "approval/list", "Files", "menu", "workflow:instance:list", []),
        ("approval.detail", "申请详情", "detail/:id", "approval/detail", "", "menu", "workflow:instance:retrieve", []),
        ("approval.task", "审批任务", "task", "approval/task", "Stamp", "menu", "workflow:instance:approve", []),
        ("approval.template", "流程模板", "template", "approval/template", "SetUp", "menu", "workflow:template:list", []),
        ("approval.designer", "流程设计器", "designer/:id?", "approval/designer", "Connection", "menu", "workflow:template:update", []),
        ("approval.diff", "模板版本对比", "diff/:id", "approval/diff", "Switch", "menu", "workflow:template:list", []),
        ("approval.sandbox", "流程沙盘回放", "sandbox", "approval/sandbox", "VideoPlay", "menu", "workflow:replay:run", []),
        ("approval.health", "流程健康度", "health", "approval/health", "TrendCharts", "menu", "workflow:health:view", []),
    ]),
    ("attendance", "考勤管理", "/attendance", "Layout", "Clock", "dir", "", [
        ("attendance.punch", "打卡", "punch", "attendance/punch", "Location", "menu", "attendance:punch:create", []),
        ("attendance.mine", "我的考勤", "mine", "attendance/mine", "Calendar", "menu", "attendance:record:list", []),
        ("attendance.rule", "考勤规则", "rule", "attendance/rule", "Setting", "menu", "attendance:rule:list", []),
        ("attendance.exception", "异常考勤", "exception", "attendance/exception", "Warning", "menu", "attendance:exception:list", []),
        ("attendance.dept", "部门汇总", "dept", "attendance/dept", "DataAnalysis", "menu", "attendance:summary:dept", []),
        ("attendance.report", "考勤报表", "report", "attendance/report", "Download", "menu", "attendance:record:export", []),
    ]),
    ("announcement", "公告文档", "/announcement", "Layout", "Bell", "dir", "", [
        ("announcement.list", "公告列表", "list", "announcement/list", "Bell", "menu", "announcement:list", []),
        ("announcement.detail", "公告详情", "detail/:id", "announcement/detail", "", "menu", "announcement:list", []),
        ("announcement.edit", "发布公告", "edit/:id?", "announcement/edit", "Edit", "menu", "announcement:create", []),
        ("announcement.stats", "阅读统计", "stats", "announcement/stats", "PieChart", "menu", "announcement:stats", []),
        ("announcement.doc", "文档中心", "doc", "announcement/doc", "FolderOpened", "menu", "document:list", []),
    ]),
    ("hr", "人事管理", "/hr", "Layout", "User", "dir", "", [
        ("hr.staff", "员工档案", "staff", "hr/staff", "User", "menu", "hr:staff:list", []),
        ("hr.staffDetail", "员工详情", "staff/:id", "hr/staffDetail", "", "menu", "hr:staff:list", []),
        ("hr.transfer", "入转调离", "transfer", "hr/transfer", "Refresh", "menu", "hr:transfer:list", []),
        ("hr.contract", "合同管理", "contract", "hr/contract", "Tickets", "menu", "hr:contract:list", []),
        ("hr.training", "培训记录", "training", "hr/training", "Reading", "menu", "hr:training:list", []),
        ("hr.analytics", "员工结构分析", "analytics", "hr/analytics", "Histogram", "menu", "hr:analytics:view", []),
    ]),
    ("expense", "财务报销", "/expense", "Layout", "Money", "dir", "", [
        ("expense.apply", "报销申请", "apply", "expense/apply", "EditPen", "menu", "expense:apply", []),
        ("expense.audit", "报销审核", "audit", "expense/audit", "Stamp", "menu", "expense:audit", []),
        ("expense.payment", "支付跟踪", "payment", "expense/payment", "Wallet", "menu", "expense:list", []),
        ("expense.stats", "报销统计", "stats", "expense/stats", "DataLine", "menu", "expense:stats", []),
    ]),
    ("meeting", "会议任务", "/meeting", "Layout", "Monitor", "dir", "", [
        ("meeting.room", "会议室", "room", "meeting/room", "OfficeBuilding", "menu", "meeting:room:list", []),
        ("meeting.booking", "会议预约", "booking", "meeting/booking", "Calendar", "menu", "meeting:booking:list", []),
        ("meeting.minute", "会议纪要", "minute", "meeting/minute", "Notebook", "menu", "meeting:minute:list", []),
        ("meeting.task", "任务看板", "task", "meeting/task", "Grid", "menu", "schedule:task:list", []),
    ]),
    ("message", "消息中心", "/message", "Layout", "ChatDotRound", "dir", "", [
        ("message.center", "消息中心", "center", "message/center", "ChatDotRound", "menu", "message:list", []),
    ]),
    ("insight", "智能分析", "/insight", "Layout", "TrendCharts", "dir", "", [
        ("insight.risk", "审批风险看板", "risk", "insight/risk", "WarningFilled", "menu", "insight:risk:view", []),
        ("insight.sla", "时效预测分析", "sla", "insight/sla", "Timer", "menu", "insight:sla:view", []),
        ("insight.bottleneck", "流程瓶颈分析", "bottleneck", "insight/bottleneck", "Histogram", "menu", "insight:bottleneck:view", []),
    ]),
    ("lowcode", "低代码配置", "/lowcode", "Layout", "MagicStick", "dir", "", [
        ("lowcode.form", "表单管理", "form", "lowcode/form", "List", "menu", "lowcode:form:list", []),
        ("lowcode.design", "表单设计器", "design/:id?", "lowcode/design", "Edit", "menu", "lowcode:form:update", []),
    ]),
    ("system", "系统管理", "/system", "Layout", "Tools", "dir", "", [
        ("system.user", "用户管理", "user", "system/user", "UserFilled", "menu", "accounts:user:list", []),
        ("system.role", "角色管理", "role", "system/role", "Avatar", "menu", "accounts:role:list", []),
        ("system.permission", "权限分配", "permission", "system/permission", "Key", "menu", "accounts:permission:list", []),
        ("system.sandbox", "权限沙盘", "sandbox", "system/sandbox", "Aim", "menu", "accounts:sandbox:simulate", []),
        ("system.dept", "组织架构", "dept", "system/dept", "OfficeBuilding", "menu", "accounts:dept:list", []),
        ("system.position", "岗位管理", "position", "system/position", "Postcard", "menu", "accounts:position:list", []),
        ("system.menu", "菜单管理", "menu", "system/menu", "Menu", "menu", "accounts:menu:list", []),
        ("system.dict", "数据字典", "dict", "system/dict", "Collection", "menu", "system:dict:list", []),
        ("system.oplog", "操作日志", "oplog", "system/oplog", "Document", "menu", "accounts:oplog:list", []),
        ("system.loginlog", "登录日志", "loginlog", "system/loginlog", "Clock", "menu", "accounts:loginlog:list", []),
        ("system.backup", "数据备份", "backup", "system/backup", "Box", "menu", "system:backup:run", []),
        ("system.param", "系统参数", "param", "system/param", "Setting", "menu", "accounts:param:list", []),
    ]),
    ("profile", "个人中心", "/profile", "Layout", "User", "dir", "", [
        ("profile.index", "个人信息", "index", "profile/index", "User", "menu", "", []),
        ("profile.password", "修改密码", "password", "profile/password", "Lock", "menu", "", []),
        ("profile.notify", "通知偏好", "notify", "profile/notify", "Bell", "menu", "", []),
        ("profile.grants", "二次授权记录", "grants", "profile/grants", "Key", "menu", "", []),
    ]),
]

# ---------------------------------------------------------------- 角色
ROLES = [
    ("admin", "系统管理员", "ALL", "系统全部功能"),
    ("employee", "普通员工", "SELF", "个人办公相关功能"),
    ("manager", "部门主管", "DEPT_TREE", "本部门及下级管理功能"),
    ("hr", "人力资源", "DEPT_TREE", "人事档案与考勤管理"),
    ("finance", "财务人员", "DEPT_TREE", "报销审核与支付"),
    ("admin_staff", "行政公告管理员", "ALL", "公告与文档管理"),
]

ROLE_PERMS = {
    "admin": ["*"],
    "employee": [
        "workflow:instance:list", "workflow:instance:retrieve", "workflow:instance:create", "workflow:instance:revoke", "workflow:instance:urge",
        "workflow:task:list", "workflow:template:list",
        "attendance:punch:create", "attendance:punch:list", "attendance:record:list",
        "attendance:summary:monthly",
        "announcement:list", "document:list", "document:download",
        "expense:apply", "expense:list",
        "meeting:room:list", "meeting:booking:list", "meeting:booking:create", "meeting:booking:cancel",
        "meeting:minute:list",
        "schedule:list", "schedule:create", "schedule:update", "task:list", "task:create", "task:update",
        "message:list", "message:read",
    ],
    "manager": [
        "workflow:instance:list", "workflow:instance:create", "workflow:instance:approve", "workflow:instance:revoke",
        "workflow:instance:urge", "workflow:task:list", "workflow:template:list", "workflow:health:view",
        "attendance:punch:create", "attendance:punch:list", "attendance:record:list", "attendance:record:export",
        "attendance:exception:list", "attendance:exception:handle", "attendance:summary:dept",
        "attendance:summary:monthly", "attendance:rule:list",
        "announcement:list", "document:list", "document:download",
        "expense:apply", "expense:list", "expense:audit", "expense:stats",
        "meeting:room:list", "meeting:booking:list", "meeting:booking:create", "meeting:booking:cancel",
        "meeting:minute:list", "meeting:minute:upload",
        "schedule:list", "schedule:create", "schedule:update", "task:list", "task:create", "task:update",
        "message:list", "message:read",
        "insight:risk:view", "insight:sla:view", "insight:bottleneck:view",
    ],
    "hr": [
        "accounts:user:list", "accounts:dept:list", "accounts:position:list", "accounts:role:list",
        "hr:staff:list", "hr:staff:update", "hr:transfer:list", "hr:transfer:create",
        "hr:contract:list", "hr:contract:create", "hr:contract:update", "hr:contract:destroy",
        "hr:training:list", "hr:training:create", "hr:training:update", "hr:training:destroy",
        "hr:analytics:view",
        "attendance:record:list", "attendance:record:export", "attendance:record:rebuild",
        "attendance:rule:list", "attendance:rule:update", "attendance:rule:create", "attendance:rule:destroy",
        "attendance:punch:list", "attendance:punch:create",
        "attendance:exception:list", "attendance:exception:handle", "attendance:summary:dept",
        "attendance:summary:monthly",
        "workflow:instance:approve", "workflow:task:list", "workflow:instance:list", "workflow:health:view",
        "announcement:list", "document:list", "document:upload", "document:download", "document:share",
        "sensitive:plaintext:view", "sensitive:grant",
        "accounts:sensitive:grant", "accounts:sensitive:logs",
        "message:list", "message:read", "task:list",
        "insight:bottleneck:view",
    ],
    "finance": [
        "expense:apply", "expense:list", "expense:audit", "expense:pay", "expense:stats",
        "workflow:instance:approve", "workflow:task:list", "workflow:instance:list",
        "announcement:list", "document:list", "document:download",
        "attendance:record:list", "message:list", "message:read",
    ],
    "admin_staff": [
        "announcement:list", "announcement:create", "announcement:update", "announcement:destroy", "announcement:stats",
        "document:list", "document:upload", "document:destroy", "document:download", "document:share",
        "document:update",
        "meeting:room:list", "meeting:room:update", "meeting:room:create", "meeting:room:destroy",
        "meeting:booking:list", "meeting:booking:create", "meeting:booking:cancel",
        "meeting:minute:list", "meeting:minute:upload",
        "attendance:record:list", "attendance:record:export", "attendance:summary:dept",
        "schedule:list", "schedule:create", "schedule:update", "task:list", "task:create", "task:update",
        "workflow:instance:list", "workflow:task:list",
        "accounts:param:list", "accounts:param:update", "system:dict:list", "system:dict:update",
        "message:list", "message:read",
    ],
}

# ---------------------------------------------------------------- 权限点自动补全
# 视图集的 PermCodeMixin 会按 action 推导权限码（如 expense:retrieve / workflow:task:create），
# 若这些推导出的码未在 PERMISSIONS 中登记，会导致接口对普通角色永久 403。
# 这里按视图集真实的 perm_prefix 补齐标准 CRUD 权限点并登记，使菜单可见、接口可用；
# 未登记的危险动作仍默认拒绝（管理员由 * 通配放行）。
from apps.common.rbac_introspect import collect_perm_prefixes, referenced_codes as _referenced_codes

for _p in sorted(collect_perm_prefixes()):
    for _a in ("list", "create", "retrieve", "update", "partial_update", "destroy"):
        _c = f"{_p}:{_a}"
        if not any(_c == _existing[1] for _existing in PERMISSIONS):
            PERMISSIONS.append((_c.split(":")[0], _c, _c.split(":")[-1], "api"))

# 菜单/角色引用但未登记的权限码也一并补全登记
for _c in sorted(_referenced_codes()):
    if not any(_c == _existing[1] for _existing in PERMISSIONS):
        PERMISSIONS.append((_c.split(":")[0], _c, _c.split(":")[-1], "api"))


def _expand_role_codes(role_code: str, codes: set) -> set:
    """按角色已有权限，自动补齐该 perm_prefix 下的标准 CRUD 授权。"""
    prefixes = {c.rsplit(":", 1)[0] for c in codes if ":" in c}
    out = set(codes)
    for p in prefixes:
        if f"{p}:list" in codes or f"{p}:create" in codes:
            out.add(f"{p}:retrieve")
        if f"{p}:update" in codes or f"{p}:create" in codes:
            out.update({f"{p}:update", f"{p}:partial_update", f"{p}:destroy"})
    return out


# ---------------------------------------------------------------- 组织
DEPARTMENTS = [
    ("H00", "总部", None),
    ("H01", "研发中心", "H00"),
    ("H02", "市场中心", "H00"),
    ("H03", "财务中心", "H00"),
    ("H04", "人力行政中心", "H00"),
    ("H05", "运营中心", "H00"),
    ("D0101", "后端研发部", "H01"),
    ("D0102", "前端研发部", "H01"),
    ("D0103", "测试部", "H01"),
    ("D0201", "销售一部", "H02"),
    ("D0202", "销售二部", "H02"),
    ("D0203", "品牌部", "H02"),
    ("D0301", "会计核算部", "H03"),
    ("D0302", "资金管理部", "H03"),
    ("D0401", "人力资源部", "H04"),
    ("D0402", "行政部", "H04"),
    ("D0501", "客户成功部", "H05"),
    ("D0502", "数据运营部", "H05"),
]


class Command(BaseCommand):
    help = "初始化权限点、角色、菜单、组织架构与管理员账号"

    def add_arguments(self, parser):
        parser.add_argument("--password", default="Oa@123456", help="初始密码")
        parser.add_argument("--reset", action="store_true", help="重置菜单与权限点（保留用户）")
        parser.add_argument("--force-perms", action="store_true", help="强制按 ROLE_PERMS 重新覆盖角色权限")

    @transaction.atomic
    def handle(self, *args, **opts):
        pwd = opts["password"]
        self._init_permissions()
        self._init_roles(force=opts["force_perms"])
        self._init_menus(reset=opts["reset"])
        self._init_departments()
        self._init_positions()
        self._init_users(pwd)
        self._init_params()
        self.stdout.write(self.style.SUCCESS("init_base 完成"))

    def _init_permissions(self):
        created = 0
        for module, code, name, kind in PERMISSIONS:
            _, ok = Permission.objects.get_or_create(
                code=code, defaults={"name": name, "module": module, "kind": kind}
            )
            created += 1 if ok else 0
        self.stdout.write(f"  权限点：新增 {created} / 总计 {Permission.objects.count()}")

    def _init_roles(self, force=False):
        created = 0
        all_perms = list(Permission.objects.all())
        for code, name, scope, desc in ROLES:
            role, ok = Role.objects.get_or_create(
                code=code, defaults={"name": name, "data_scope": scope, "description": desc}
            )
            created += 1 if ok else 0
            if ok or force or role.permissions.count() == 0:
                if code == "admin":
                    role.permissions.set(all_perms)
                else:
                    codes = _expand_role_codes(code, set(ROLE_PERMS.get(code, [])))
                    role.permissions.set(Permission.objects.filter(code__in=codes))
        self.stdout.write(f"  角色：新增 {created} / 总计 {Role.objects.count()}")

    def _init_menus(self, reset=False):
        if reset:
            Menu.objects.all().delete()
        created = 0

        def walk(nodes, parent):
            nonlocal created
            for idx, (code, name, path, component, icon, mtype, perm, children) in enumerate(nodes):
                menu, ok = Menu.objects.get_or_create(
                    code=code,
                    defaults={
                        "name": name, "parent": parent, "path": path, "component": component,
                        "icon": icon, "type": mtype, "permission_code": perm, "sort": idx,
                        "visible": not path.endswith(":id") and ":id?" not in path and mtype != "button",
                    },
                )
                created += 1 if ok else 0
                walk(children, menu)

        walk(MENUS, None)
        self.stdout.write(f"  菜单：新增 {created} / 总计 {Menu.objects.count()}")

    def _init_departments(self):
        by_code = {}
        for code, name, parent_code in DEPARTMENTS:
            parent = by_code.get(parent_code)
            dept, _ = Department.objects.get_or_create(code=code, defaults={"name": name, "parent": parent, "sort": 0})
            by_code[code] = dept
        self.stdout.write(f"  部门：总计 {Department.objects.count()}")

    def _init_positions(self):
        specs = [
            ("P01", "技术总监", "H01"), ("P02", "后端工程师", "D0101"), ("P03", "前端工程师", "D0102"),
            ("P04", "测试工程师", "D0103"), ("P05", "销售经理", "D0201"), ("P06", "销售代表", "D0201"),
            ("P07", "品牌专员", "D0203"), ("P08", "会计", "D0301"), ("P09", "财务经理", "H03"),
            ("P10", "HRBP", "D0401"), ("P11", "行政专员", "D0402"), ("P12", "运营专员", "D0501"),
            ("P13", "数据分析师", "D0502"), ("P14", "总经理", "H00"),
        ]
        for code, name, dept_code in specs:
            dept = Department.objects.filter(code=dept_code).first()
            Position.objects.get_or_create(code=code, defaults={"name": name, "dept": dept})
        self.stdout.write(f"  岗位：总计 {Position.objects.count()}")

    def _init_users(self, pwd):
        hq = Department.objects.filter(code="H00").first()
        admin, ok = User.objects.get_or_create(
            username="admin",
            defaults={"first_name": "系统管理员", "is_superuser": True, "is_staff": True,
                      "dept": hq, "employee_no": "E0001", "status": User.Status.ACTIVE},
        )
        admin.is_superuser = True
        admin.is_staff = True
        admin.set_password(pwd)
        admin.must_change_pwd = False
        admin.save()
        admin_role = Role.objects.filter(code="admin").first()
        if admin_role:
            UserRole.objects.get_or_create(user=admin, role=admin_role, defaults={"is_primary": True})

        demos = [
            ("zhangwei", "张伟", "manager", "D0101", "P02", "E1001"),
            ("lina", "李娜", "hr", "D0401", "P10", "E1002"),
            ("wangfang", "王芳", "finance", "D0301", "P08", "E1003"),
            ("liuyang", "刘洋", "employee", "D0101", "P02", "E1004"),
            ("chenjing", "陈静", "employee", "D0102", "P03", "E1005"),
            ("zhaolei", "赵磊", "manager", "D0201", "P05", "E1006"),
            ("sunli", "孙丽", "admin_staff", "D0402", "P11", "E1007"),
        ]
        for username, name, role_code, dept_code, pos_code, emp_no in demos:
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={"first_name": name, "dept": Department.objects.filter(code=dept_code).first(),
                          "position": Position.objects.filter(code=pos_code).first(),
                          "employee_no": emp_no},
            )
            user.set_password(pwd)
            user.is_staff = False
            user.must_change_pwd = False
            user.save()
            role = Role.objects.filter(code=role_code).first()
            if role:
                UserRole.objects.get_or_create(user=user, role=role, defaults={"is_primary": True})
        self.stdout.write(f"  用户：总计 {User.objects.count()}（admin + 7 个演示账号，密码均为 {pwd}）")

    def _init_params(self):
        defaults = [
            ("LOGIN_CAPTCHA_REQUIRED", "1", "登录是否需要图形验证码", "1=需要，0=关闭"),
            ("ATTENDANCE_WORK_START", "09:00", "上班时间", ""),
            ("ATTENDANCE_WORK_END", "18:00", "下班时间", ""),
            ("SLA_WARNING_HOURS", "24", "审批超时预警小时数", ""),
            ("COMPANY_NAME", "示例科技有限公司", "公司名称", ""),
        ]
        for key, value, name, remark in defaults:
            SystemParam.objects.get_or_create(key=key, defaults={"value": value, "name": name, "remark": remark})
        self.stdout.write(f"  系统参数：总计 {SystemParam.objects.count()}")
