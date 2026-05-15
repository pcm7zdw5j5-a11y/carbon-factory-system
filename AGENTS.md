# AGENTS.md

本文件给后续维护者和 AI 编码助手使用。修改本项目时必须先阅读本文件。

## 项目定位

这是“碳纤维工厂订单管理系统 V1”，运行方式是 Python Flask + SQLite，主电脑启动服务，局域网内其他电脑和手机通过浏览器访问。

## 不能破坏的功能

修改前必须确认不会影响：

- 登录和退出登录
- 多账号与角色权限
- 订单新建、编辑、详情、删除
- 图纸上传、查看、下载
- 自动报价
- 成本、利润、毛利率核算
- 订单状态“下一步”
- 取消订单
- 状态变更历史
- 价格表管理
- 用户管理
- 月度统计
- 月度统计打印
- 生产单查看和打印
- 手机端布局和底部导航
- 订单列表实时筛选
- 一键备份

严禁删除或清空：

- `carbon_factory.db`
- `uploads/`
- `backups/`

## 代码结构规则

- Flask 入口：`app.py`
- 应用创建：`app/__init__.py`
- 路由：`app/routes.py`
- 数据库初始化：`app/database.py`
- 数据库读写：`app/repositories.py`
- 权限：`app/auth.py`
- 报价成本计算：`app/services/pricing.py`
- 模板：`templates/`
- 样式：`static/style.css`
- 页面 JS：`static/app.js`、`static/js/`

不要把业务逻辑写进模板。不要把数据库 SQL 散落到前端文件。

## 静态文件规则

CSS 必须使用：

```html
<link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
```

全局 JS 必须使用：

```html
<script src="{{ url_for('static', filename='app.js') }}"></script>
```

浏览器访问下面地址必须能看到 CSS 代码：

```text
http://127.0.0.1:5000/static/style.css
```

## UI 规则

整体风格：

- 现代后台
- 简洁专业
- 工厂订单系统
- 绿色主色调
- 电脑端和手机端都可用

主色调：

- 主色：`#0F766E`
- 主色浅色：`#CCFBF1`
- 页面背景：`#F3F4F6`
- 卡片背景：`#FFFFFF`
- 文字主色：`#111827`
- 文字次色：`#6B7280`
- 边框色：`#E5E7EB`
- 危险色：`#DC2626`

页面布局：

- 电脑端：左侧侧边栏 + 右侧内容区
- 手机端：隐藏侧边栏，保留顶部短标题和底部导航
- 手机端禁止横向溢出
- 月度统计手机端汇总数据必须使用卡片或单列列表，不能使用宽表格

组件要求：

- 卡片使用统一白底、圆角、边框、轻阴影
- 按钮使用统一 `.button` / `.primary` / `.secondary` / `.danger`
- 表格使用统一表头、边框、hover 效果
- 状态必须使用 `.status-badge[data-status="状态"]`
- 打印时隐藏导航、按钮、筛选控件

## 权限规则

角色：

- `admin`：所有功能
- `sales`：订单、报价、图纸、销售阶段状态
- `production`：订单查看、生产单、生产阶段状态
- `finance`：成本、利润、月度统计

没有权限的菜单和按钮不要显示。直接访问无权限页面必须返回“无权限访问”。

## 数据安全规则

- 密码必须使用哈希，不能明文保存
- Flask session 是每个浏览器独立的，不要改成全局登录状态
- SQLite 连接必须带 timeout
- 每个请求独立数据库连接，请求结束关闭
- 状态“下一步”必须校验提交时状态，防止多人同时点击导致跳级
- 大改前必须按 `BACKUP_RULES.md` 备份

## 测试规则

改代码后必须运行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

通过后再交付。若测试失败，不能声称完成。

建议重点检查：

- `tests/test_auth.py`
- `tests/test_status_flow.py`
- `tests/test_uploads.py`
- `tests/test_statistics_print.py`
- `tests/test_responsive.py`
- `tests/test_static_assets.py`
- `tests/test_backup.py`

## Git 规则

每次功能修改建议：

1. 先备份
2. 修改代码
3. 运行测试
4. 查看变更
5. 提交 Git
6. 更新 `CHANGELOG.md`

提交信息要清楚说明修改目的。
