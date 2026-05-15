# BACKUP_RULES.md

本文件说明每次大改前如何备份，防止误删订单、图纸和代码。

## 什么时候必须备份

以下情况开始前必须备份：

- 修改数据库结构
- 修改订单、报价、成本、权限、登录逻辑
- 大范围修改模板或 CSS
- 修改上传、下载、打印、备份功能
- 批量改文件
- 准备提交稳定版本前

## 必须备份的内容

每次大改前至少备份：

- `carbon_factory.db`
- `uploads/`
- `app.py`
- `app/`
- `templates/`
- `static/`
- `README.md`
- `AGENTS.md`
- `CHANGELOG.md`

## 推荐方式一：系统内一键备份

1. 用 `admin` 登录系统。
2. 打开首页。
3. 点击“一键备份”。
4. 系统会在 `backups/` 文件夹生成 zip 文件。
5. zip 文件包含：
   - `carbon_factory.db`
   - `uploads/`

注意：系统内一键备份主要备份业务数据，不一定包含全部代码文件。大改代码前还要做“推荐方式二”。

## 推荐方式二：手动完整备份

在 PowerShell 中运行：

```powershell
cd "D:\Documents\New project 2"
$time = Get-Date -Format "yyyyMMdd_HHmmss"
$dest = "backups\code_backup_$time"
New-Item -ItemType Directory -Force -Path $dest
Copy-Item -LiteralPath "carbon_factory.db" -Destination $dest -ErrorAction SilentlyContinue
Copy-Item -LiteralPath "uploads" -Destination $dest -Recurse -ErrorAction SilentlyContinue
Copy-Item -LiteralPath "app.py" -Destination $dest -ErrorAction SilentlyContinue
Copy-Item -LiteralPath "app" -Destination $dest -Recurse -ErrorAction SilentlyContinue
Copy-Item -LiteralPath "templates" -Destination $dest -Recurse -ErrorAction SilentlyContinue
Copy-Item -LiteralPath "static" -Destination $dest -Recurse -ErrorAction SilentlyContinue
Copy-Item -LiteralPath "README.md" -Destination $dest -ErrorAction SilentlyContinue
Copy-Item -LiteralPath "AGENTS.md" -Destination $dest -ErrorAction SilentlyContinue
Copy-Item -LiteralPath "CHANGELOG.md" -Destination $dest -ErrorAction SilentlyContinue
```

## 备份命名规则

备份文件名必须带日期时间，例如：

```text
carbon_factory_backup_20260514_153000.zip
code_backup_20260514_153000
```

## 恢复原则

恢复前不要直接覆盖当前文件。先把当前目录再备份一次，然后从备份里复制需要恢复的文件。

## Git 配合规则

如果 Git 可用：

1. 备份业务数据。
2. 运行测试。
3. 提交当前稳定版本。
4. 再开始大改。

示例：

```powershell
git status
git add .
git commit -m "V1 stable before next changes"
```
