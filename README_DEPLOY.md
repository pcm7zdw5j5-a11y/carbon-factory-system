# AWS Lightsail 部署说明

本文档用于把“碳纤维工厂订单管理系统 V1”部署到 AWS Lightsail 做线上测试。

## 重要提醒

- 不要把 `.env` 上传到 GitHub。
- 不建议把正式的 `carbon_factory.db` 上传到公开 GitHub。
- 不建议把正式的 `uploads/` 上传到公开 GitHub。
- 部署前请先备份 `carbon_factory.db` 和 `uploads/`。
- 当前 SQLite 适合少量员工测试使用；如果后续多人高频使用，建议升级 PostgreSQL 或 MySQL。

## 一、准备 GitHub 仓库

当前项目已经准备好 `.gitignore`，会忽略：

```text
.venv/
__pycache__/
.env
backups/
*.log
carbon_factory.db
uploads/
```

如果要上传 GitHub：

```powershell
cd "D:\Documents\New project 2"
git init
git add .
git commit -m "Prepare for GitHub and AWS Lightsail deploy"
git branch -M main
git remote add origin https://github.com/你的用户名/你的仓库名.git
git push -u origin main
```

如果你需要把现有真实数据库和图纸也传到服务器，请用压缩包或安全传输方式单独上传，不要提交到公开仓库。

## 二、创建 AWS Lightsail 实例

1. 登录 AWS 控制台。
2. 打开 Lightsail。
3. 创建实例。
4. 平台选择 Linux/Unix。
5. 系统建议选择 Ubuntu LTS。
6. 选择合适套餐。
7. 创建后进入 Networking，放行端口：
   - `22`：SSH
   - `80`：HTTP
   - `443`：HTTPS，后续配置证书时使用
   - `5000`：仅测试时可临时放行，正式建议通过 Nginx 代理到 80

## 三、登录服务器

使用 Lightsail 网页 SSH，或者在本机用 SSH 登录：

```bash
ssh ubuntu@你的服务器公网IP
```

## 四、安装系统依赖

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git nginx
```

## 五、下载项目代码

方式 A：从 GitHub 克隆：

```bash
cd /var/www
sudo git clone https://github.com/你的用户名/你的仓库名.git carbon_factory
sudo chown -R ubuntu:ubuntu /var/www/carbon_factory
cd /var/www/carbon_factory
```

方式 B：不使用 GitHub，直接上传压缩包：

1. 在本机把项目压缩。
2. 上传到服务器。
3. 解压到 `/var/www/carbon_factory`。

## 六、创建虚拟环境并安装依赖

```bash
cd /var/www/carbon_factory
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt
```

## 七、配置环境变量

创建 `.env` 文件：

```bash
nano /var/www/carbon_factory/.env
```

写入：

```bash
SECRET_KEY=请换成一串很长的随机字符串
DATABASE=/var/www/carbon_factory/carbon_factory.db
UPLOAD_FOLDER=/var/www/carbon_factory/uploads
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=0
```

保存后创建上传目录：

```bash
mkdir -p /var/www/carbon_factory/uploads
mkdir -p /var/www/carbon_factory/backups
```

说明：

- `SECRET_KEY` 必须改成你自己的随机字符串。
- `FLASK_DEBUG=0`，正式部署不要开启 debug。
- 如果 `carbon_factory.db` 不存在，系统启动时会自动创建。
- 如果 `users` 表不存在，系统启动时会自动创建。
- 如果 admin 用户不存在，系统启动时才会创建默认 `admin / admin123`。
- 已有数据库不会被覆盖。

## 八、手动测试 gunicorn

```bash
cd /var/www/carbon_factory
set -a
source .env
set +a
./.venv/bin/gunicorn -w 2 -b 0.0.0.0:5000 app:app
```

然后浏览器打开：

```text
http://服务器公网IP:5000
```

确认能打开后，按 `Ctrl + C` 停止 gunicorn。

说明：本项目采用 Flask 工厂结构，`app/__init__.py` 会导出 `app` 对象，`app.py` 也导入同一个对象用于本地运行，因此可以使用：

```bash
gunicorn app:app
```

## 九、配置 systemd 后台运行

创建服务文件：

```bash
sudo nano /etc/systemd/system/carbon_factory.service
```

写入：

```ini
[Unit]
Description=Carbon Factory Order Management System
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/var/www/carbon_factory
EnvironmentFile=/var/www/carbon_factory/.env
ExecStart=/var/www/carbon_factory/.venv/bin/gunicorn -w 2 -b 127.0.0.1:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable carbon_factory
sudo systemctl start carbon_factory
sudo systemctl status carbon_factory
```

查看日志：

```bash
journalctl -u carbon_factory -f
```

## 十、配置 Nginx

创建配置：

```bash
sudo nano /etc/nginx/sites-available/carbon_factory
```

写入：

```nginx
server {
    listen 80;
    server_name 你的域名或服务器公网IP;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

启用配置：

```bash
sudo ln -s /etc/nginx/sites-available/carbon_factory /etc/nginx/sites-enabled/carbon_factory
sudo nginx -t
sudo systemctl reload nginx
```

浏览器打开：

```text
http://服务器公网IP
```

## 十一、上传已有数据库和图纸

如果你要把本机已有数据放到服务器：

1. 停止服务：

```bash
sudo systemctl stop carbon_factory
```

2. 上传并覆盖：

```text
/var/www/carbon_factory/carbon_factory.db
/var/www/carbon_factory/uploads/
```

3. 修复权限：

```bash
sudo chown -R ubuntu:www-data /var/www/carbon_factory
chmod -R 775 /var/www/carbon_factory/uploads
```

4. 启动服务：

```bash
sudo systemctl start carbon_factory
```

## 十二、备份和恢复

备份：

```bash
cd /var/www/carbon_factory
mkdir -p backups
tar -czf backups/carbon_factory_$(date +%Y%m%d_%H%M%S).tar.gz carbon_factory.db uploads
```

恢复：

```bash
sudo systemctl stop carbon_factory
tar -xzf backups/你的备份文件.tar.gz -C /var/www/carbon_factory
sudo systemctl start carbon_factory
```

## 十三、更新代码

如果使用 GitHub：

```bash
cd /var/www/carbon_factory
git pull
./.venv/bin/pip install -r requirements.txt
sudo systemctl restart carbon_factory
```

更新后检查：

```bash
sudo systemctl status carbon_factory
journalctl -u carbon_factory -n 80
```

## 十四、默认登录

```text
用户名：admin
密码：admin123
```

第一次登录后，请立刻修改默认密码。
