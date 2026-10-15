# 碳纤维工厂订单管理系统 V1

这是一个基于 Python Flask + SQLite 的工厂订单管理系统。当前版本适合在主电脑或小型云服务器上运行，员工通过电脑或手机浏览器访问。项目会继续迭代，因此当前整理目标是：保留已有功能，补齐部署配置，保持结构清晰，方便后续扩展。

## 许可证

本项目采用 [MIT License](LICENSE)。

## 当前主要功能

- 登录、退出登录、多账号和角色权限
- 订单新建、编辑、详情、删除
- 图纸上传、查看、下载
- 多附件订单归档
- 自动报价、成本、利润、毛利率核算
- 订单状态“下一步”和取消订单
- 状态变更历史
- 客户管理和老客户历史价格提醒
- 价格表管理、库存安全库存和采购提醒
- 发货管理
- 生产单查看和打印
- 生产看板
- 月度统计和月度报表打印
- 淘宝订单 Excel/CSV 导入
- 标准矩形件用板计算
- 待办提醒、利润预警、异常订单记录、操作日志
- 手机端底部导航和响应式页面
- 一键备份数据库和上传文件

## 项目结构

```text
项目根目录/
├─ app.py                         # 本地启动入口，导入 app 包暴露的 Flask 实例
├─ app/
│  ├─ __init__.py                  # Flask 应用创建、配置、权限注入，并导出 gunicorn app:app
│  ├─ auth.py                      # 登录、角色、权限判断
│  ├─ config.py                    # 订单状态、来源、默认价格
│  ├─ database.py                  # SQLite 连接、初始化、自动迁移
│  ├─ filters.py                   # 模板格式化过滤器
│  ├─ repositories.py              # 数据库读写
│  ├─ routes.py                    # 当前主要页面路由
│  └─ services/
│     ├─ pricing.py                # 报价、成本、利润计算
│     ├─ statistics.py             # 月度统计计算
│     ├─ board_calculator.py       # 矩形件用板计算
│     ├─ profit_alerts.py          # 利润预警
│     └─ taobao_import.py          # 淘宝订单表格导入
├─ templates/                      # 页面模板
├─ static/                         # CSS 和 JS
├─ uploads/                        # 上传图纸和订单附件
├─ backups/                        # 备份文件
├─ tests/                          # 自动化测试
├─ requirements.txt                # Python 依赖
├─ .env.example                    # 环境变量示例
├─ .gitignore                      # Git 忽略规则
├─ AGENTS.md                       # 后续维护规则
├─ BACKUP_RULES.md                 # 大改前备份规则
└─ carbon_factory.db               # SQLite 数据库
```

当前项目还没有完全拆成多个 `routes/` 模块。为了降低风险，V1 先保持现有路由结构；后续功能变多时，可以逐步把订单、客户、统计、用户管理拆成独立 Blueprint。

## 本地运行

1. 进入项目目录：

```powershell
cd "D:\Documents\New project 2"
```

2. 安装依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

3. 启动系统：

```powershell
.\.venv\Scripts\python.exe app.py
```

4. 浏览器打开：

```text
http://127.0.0.1:5000
```

手机访问时，手机和电脑必须在同一个 Wi-Fi 下，然后打开：

```text
http://电脑局域网IP:5000
```

例如：

```text
http://192.168.1.3:5000
```

## 云服务器部署

推荐 Linux 云服务器部署方式：

1. 安装 Python 3.11 或更高版本。
2. 上传整个项目目录到服务器。
3. 创建虚拟环境并安装依赖：

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

4. 设置环境变量：

```bash
# 首次启动前，在部署环境中设置持久的 SECRET_KEY 和强 INITIAL_ADMIN_PASSWORD
export DATABASE="carbon_factory.db"
export UPLOAD_FOLDER="uploads"
```

5. 使用 gunicorn 启动：

```bash
./.venv/bin/gunicorn -w 2 -b 0.0.0.0:5000 app:app
```

说明：

- `app.py` 已暴露 `app` 对象，所以可以使用 `gunicorn app:app`。
- 正式运行不要开启 `debug=True`。
- 本地直接运行 `python app.py` 时，默认 `FLASK_DEBUG=0`。
- 需要调试时再临时设置 `FLASK_DEBUG=1`。
- 云服务器需要在安全组或防火墙中放行 5000 端口，或使用 Nginx 反向代理到 80/443。

## 首次管理员账号

首次启动前设置 `INITIAL_ADMIN_PASSWORD`，长度至少 12 个字符。系统仅在数据库中不存在 `admin` 用户时使用它创建管理员；已有管理员密码不会被覆盖。请勿把真实密码提交到 GitHub。若未设置此变量且数据库中没有管理员，系统不会创建默认账号。

`SECRET_KEY` 应设置为独一无二且持久的随机值；未设置时应用会为当前进程生成随机值，重启或多进程运行会使登录会话失效。

## 新增员工账号

1. 使用 `admin` 登录。
2. 进入“用户管理”。
3. 填写用户名、初始密码、角色。
4. 支持角色：
   - `admin`：管理员
   - `sales`：销售/客服
   - `production`：生产/板房
   - `finance`：财务

## 数据库和迁移机制

数据库文件：

```text
carbon_factory.db
```

系统启动时会自动执行安全初始化：

- 如果数据库不存在，会自动创建。
- 如果缺少表，会自动创建。
- 如果缺少字段，会自动补充。
- 如果 `admin` 用户不存在，且已配置 `INITIAL_ADMIN_PASSWORD`，才会创建管理员。
- 不会重建订单表。
- 不会清空订单。
- 不会删除 `uploads/` 中的图纸和附件。

当前 SQLite 适合少量员工同时使用。如果后续多人高频操作，建议升级到 PostgreSQL 或 MySQL。

## 备份方法

系统内备份：

1. 使用 `admin` 登录。
2. 首页点击“一键备份”。
3. 备份文件会保存到 `backups/`。
4. 备份内容包含 `carbon_factory.db` 和 `uploads/`。

手动备份：

```powershell
cd "D:\Documents\New project 2"
Compress-Archive -Path carbon_factory.db,uploads -DestinationPath backups\manual_backup.zip -Force
```

恢复方法：

1. 停止正在运行的网站。
2. 从备份压缩包中取出 `carbon_factory.db` 覆盖项目根目录的数据库文件。
3. 从备份压缩包中取出 `uploads/` 覆盖项目根目录的上传文件夹。
4. 重新启动网站。

大改前请优先阅读：

```text
BACKUP_RULES.md
```

## 测试方法

运行全部测试：

```powershell
cd "D:\Documents\New project 2"
.\.venv\Scripts\python.exe -m pytest -q
```

测试订单流程：

1. 登录 admin 或 sales。
2. 新建订单。
3. 上传图纸。
4. 检查自动报价。
5. 保存后进入订单详情。
6. 点击“下一步”推进状态。
7. 查看状态变更历史。

测试报价：

1. 新建订单时选择规格、厚度、板数。
2. 输入切割长度、孔数、倒角、包装费、快递费。
3. 查看自动报价和最终报价。
4. 修改价格表后再新建订单，确认新价格生效。

测试状态下一步：

按顺序验证：

```text
待审核 → 待报价 → 已报价 → 已付款 → 待下板 → 加工中 → 待质检 → 待包装 → 待发货 → 已发货 → 已完成
```

测试月度统计：

1. 创建几条本月订单。
2. 填写销售额、成本和状态。
3. 进入“月度统计”。
4. 检查订单总数、销售额、成本、利润和来源统计。
5. 点击打印报表，确认打印内容正常。

## 后续功能计划

- V2：手机端适配继续优化
- V3：淘宝订单 Excel 导入增强
- V4：标准矩形件自动算板数增强
- V5：DXF 图纸识别
- V6：自动排版 nesting
- V7：库存和采购管理增强
- V8：小程序或客户自助下单

## 后续开发规则

每次让 Codex 或开发者继续改功能前，请按下面顺序：

1. 先备份 `carbon_factory.db`、`uploads/`、`app.py`、`app/`、`templates/`、`static/`。
2. 明确要改哪个功能，不要顺手重写无关页面。
3. 数据库新增字段必须写自动迁移，不能重建表。
4. 权限相关功能必须检查 admin、sales、production、finance 四种角色。
5. 修改完成后运行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

6. 测试通过后再部署。

## GitHub 状态

当前项目目录没有连接 GitHub 仓库。如果要上传 GitHub，建议先确认 `.gitignore`，不要提交：

- `.venv/`
- `__pycache__/`
- `.env`
- `carbon_factory.db`
- `uploads/`
- `backups/`
- `*.log`
