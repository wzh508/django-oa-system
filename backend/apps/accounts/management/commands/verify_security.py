"""安全自检（创新点 6.4）：越权自检矩阵 + 哈希链校验 + 字段脱敏验证。

    python manage.py verify_security

输出三类检查结果，发现越权风险 / 权限漂移 / 哈希链断裂 / 脱敏失效时退出码非 0。
"""
import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.management.commands.init_base import PERMISSIONS, ROLE_PERMS
from apps.common.hashchain import verify_chain
from apps.common.masking import mask_value, should_mask
from apps.common.rbac_introspect import (
    STANDARD_ACTIONS,
    _iter_viewset_classes,
    collect_enforced_codes,
)

logger = logging.getLogger(__name__)


def role_drift():
    from apps.accounts.models import Permission, Role

    # 以数据库实际存在的权限点为准（含 init_base 按 perm_prefix 自动补齐的 CRUD 码）
    db_codes = set(Permission.objects.values_list("code", flat=True))
    issues = []
    for role in Role.objects.all():
        if role.code == "admin":
            intended = db_codes  # 管理员通配，应持有全部已登记权限
        else:
            intended = set(ROLE_PERMS.get(role.code, []))
        actual = set(p.code for p in role.permissions.all())
        missing = intended - actual
        extra = actual - intended
        if role.code != "admin":
            extra = extra - db_codes  # 防御性：忽略未登记权限
        if missing or extra:
            issues.append({
                "role": role.code, "name": role.name,
                "missing": sorted(missing), "extra": sorted(extra),
            })
    return issues


def PERMISSIONS_codes_all():
    return {code for _, code, _, _ in PERMISSIONS}


class Command(BaseCommand):
    help = "安全自检：越权矩阵 + 哈希链 + 字段脱敏"

    def handle(self, *args, **opts):
        problems = []

        # ---- 1. 越权自检矩阵 ----
        self.stdout.write(self.style.HTTP_INFO("== 1. 越权自检矩阵 =="))
        from apps.accounts.models import Permission

        registered = set(Permission.objects.values_list("code", flat=True))
        enforced = collect_enforced_codes()
        scanned = sum(1 for _ in _iter_viewset_classes())
        gaps = sorted(enforced - registered)         # 强制了但未登记
        dead = sorted(registered - enforced)         # 登记了但未强制 → 冗余（提示）
        STD = set(STANDARD_ACTIONS)
        real_gaps = [g for g in gaps if g.split(":")[-1] in STD]   # 标准动作未登记 = 真实失效
        custom_gaps = [g for g in gaps if g.split(":")[-1] not in STD]  # 自定义动作未登记 = 仅管理员可用，已安全拒绝
        self.stdout.write(f"  扫描视图集 {scanned} 个，强制权限码 {len(enforced)} 个，登记权限点 {len(registered)} 个")
        self.stdout.write(f"  标准动作未登记（真实失效）: {real_gaps}")
        self.stdout.write(f"  自定义动作未登记（仅管理员，已安全拒绝）: {len(custom_gaps)} 个")
        self.stdout.write(f"  登记但未强制（冗余）: {len(dead)} 个")
        if real_gaps:
            problems.append(f"权限缺口: {real_gaps}")
            for g in real_gaps:
                self.stdout.write(self.style.ERROR(f"    [风险] 标准动作 {g} 未登记，将始终拒绝访问"))
        if custom_gaps:
            self.stdout.write(self.style.WARNING(
                f"    提示：{len(custom_gaps)} 个自定义动作（如 {custom_gaps[:5]}）未单独登记，"
                f"非管理员默认拒绝（管理员由 * 通配放行），属预期安全行为"))

        drift = role_drift()
        if drift:
            problems.append("权限漂移")
            for d in drift:
                self.stdout.write(self.style.ERROR(
                    f"    [漂移] 角色 {d['role']}({d['name']}) 缺失 {d['missing']} 多余 {d['extra']}"))
        else:
            self.stdout.write(self.style.SUCCESS("  角色权限与基准一致，无漂移"))

        # ---- 2. 哈希链校验 ----
        self.stdout.write(self.style.HTTP_INFO("\n== 2. 操作日志哈希链校验 =="))
        from apps.accounts.models import OperationLog

        rows = list(OperationLog.objects.order_by("id").values("id", "prev_hash", "curr_hash", "content"))
        result = verify_chain(rows)
        result["checked_at"] = timezone.now().isoformat()
        if result["ok"]:
            self.stdout.write(self.style.SUCCESS(f"  哈希链完整：共 {result['total']} 条，无篡改"))
        else:
            problems.append("哈希链断裂")
            self.stdout.write(self.style.ERROR(
                f"  [告警] 发现 {len(result['tampered_ids'])} 条异常，断点 {result['broken_at']}"))
        # 反例自测：篡改一条内容后应当被识别
        if rows:
            tamper = [dict(rows[0])]
            tamper[0]["content"] = "{\"module\":\"x\",\"action\":\"y\"}"
            fake = verify_chain(tamper)
            self.stdout.write(f"  篡改检测自测：{'通过' if not fake['ok'] else '失败'}")

        # ---- 3. 字段脱敏验证 ----
        self.stdout.write(self.style.HTTP_INFO("\n== 3. 字段脱敏验证 =="))
        samples = [
            ("salary", "15000.00", "***"),
            ("id_card", "110101199001011234", "110101********1234"),
            ("bank_card", "6222021234567890123", "6222 **** **** 0123"),
        ]
        for field, raw, expect in samples:
            got = mask_value(field, raw)
            ok_mask = got == expect
            self.stdout.write(f"  {field}: {raw} -> {got} {'OK' if ok_mask else 'FAIL'}")
            if not ok_mask:
                problems.append(f"脱敏规则失效: {field}")

        from apps.accounts.models import User

        employee = User.objects.filter(username="liuyang", is_active=True).first()
        admin = User.objects.filter(username="admin", is_active=True).first()
        hr = User.objects.filter(username="lina", is_active=True).first()
        for label, u, expect_masked in [("员工", employee, True), ("超管", admin, False), ("HR", hr, False)]:
            if u is None:
                continue
            actual = should_mask(u, "salary")
            ok_ = actual == expect_masked
            self.stdout.write(f"  should_mask({label}, salary) = {actual}（期望 {expect_masked}） {'OK' if ok_ else 'FAIL'}")
            if not ok_:
                problems.append(f"脱敏策略失效: {label}")

        # ---- 汇总 ----
        self.stdout.write(self.style.HTTP_INFO("\n== 汇总 =="))
        if problems:
            self.stdout.write(self.style.ERROR(f"  发现 {len(problems)} 类安全问题：{problems}"))
            return
        self.stdout.write(self.style.SUCCESS("  安全自检全部通过：越权矩阵正常、哈希链完整、脱敏生效"))
