# 基于 Django 的企业 OA 管理系统

> 本科毕业设计项目 ｜ 前后端分离 ｜ 12 个业务应用 ｜ 62 张数据表 ｜ 约 64 个 RESTful 接口

一套面向中小企业的办公自动化（OA）系统，覆盖组织权限、考勤、审批流、人事、文档、会议、日程、公告、站内消息与数据看板等日常办公场景，并内置低代码表单能力。系统同时配套一套接口自测脚本，用于开发阶段快速回归。

---

## 技术栈

| 层次 | 选型 |
|---|---|
| 后端框架 | Django 4.2 + Django REST Framework |
| 认证授权 | SimpleJWT + 基于角色的菜单/接口权限控制 |
| 数据库 | MySQL 8（可通过 `.env` 降级为 SQLite） |
| 缓存 / 异步 | Redis + Celery |
| 前端 | Vue 3.5 + Vite 5 + Pinia + Vue Router + Element Plus + Axios |
| 测试 | Python + httpx 接口冒烟脚本、角色权限遍历脚本 |

---

## 功能模块

| 应用 | 职责 |
|---|---|
| `accounts` | 组织架构与权限：部门、用户、角色、菜单与权限码 |
| `attendance` | 考勤：考勤规则、打卡记录、补卡申请 |
| `workflow` | 审批流：流程模板、节点与审批实例 |
| `hr` | 人事：员工档案与在职状态维护 |
| `document` | 文档：公文与附件管理 |
| `meeting` | 会议：会议室、预约与会议记录 |
| `schedule` | 日程：个人与部门日程 |
| `announcement` | 公告：发布、置顶与阅读状态 |
| `message` | 站内消息：站内通知与未读计数 |
| `insight` | 数据看板：考勤、审批等业务指标统计 |
| `lowcode` | 低代码：动态表单的定义与渲染 |
| `common` | 公共能力：基类模型、统一响应、分页与异常处理 |

系统共支撑 **8 类审批单据**落地：请假、加班、出差、补卡、报销、采购、用印、合同。

---

## 目录结构

```
project/
├── backend/                 # Django 后端
│   ├── apps/                # 12 个业务应用
│   ├── config/              # 全局配置、路由、Celery
│   ├── scripts/             # 接口冒烟测试与权限遍历脚本
│   ├── manage.py
│   └── requirements.txt
├── frontend/                # Vue3 前端
│   ├── src/
│   └── package.json
├── scripts/                 # 环境初始化与启动脚本
├── .env.example             # 环境变量模板（复制为 .env 后填写）
└── 一键启动系统.bat
```

---

## 快速开始

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填写 DJANGO_SECRET_KEY、DB_PASSWORD 等
```

> 仓库中**不包含** `.env` 与任何真实密钥，请勿把填写后的 `.env` 提交回仓库。

### 2. 启动后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

也可以在项目根目录直接运行 `一键启动系统.bat`，一次拉起前后端。

---

## 接口自测

开发阶段为了快速验证接口可用性，编写了一套不依赖 mock 的冒烟测试脚本，全部使用真实 HTTP 请求：

```bash
cd backend
python scripts/smoke.py            # 全模块冒烟
python scripts/smoke_attendance.py  # 单模块冒烟，其余同理
python scripts/role_integration.py  # 按角色遍历菜单可达接口，检查越权
```

| 脚本 | 覆盖范围 |
|---|---|
| `smoke.py` / `smoke_modules.py` | 多模块串联冒烟 |
| `smoke_attendance.py` | 考勤与补卡 |
| `smoke_workflow.py` | 审批流发起、流转与回退 |
| `smoke_expense.py` | 报销流程 |
| `smoke_hr.py` | 人事档案 |
| `smoke_insight.py` | 数据看板统计口径 |
| `smoke_lowcode.py` | 低代码表单 |
| `role_integration.py` | 角色权限遍历，定位 403 越权与 500 异常 |

所有脚本合计约 1,300 行、**123 处断言**，逐项校验响应状态码与业务字段，输出 PASS / FAIL 清单便于回归。

---

## 说明

- 本项目为本科毕业设计，部分模块仍在持续完善中。
- 数据库结构设计见 `数据字典` 与 `E-R 图` 文档（另行归档，未纳入本仓库）。
- 生产环境部署前请务必修改 `DJANGO_SECRET_KEY`、关闭 `DJANGO_DEBUG` 并按需收紧 `CORS_ALLOW_ALL_ORIGINS`。
