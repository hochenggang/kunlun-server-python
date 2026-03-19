# Kunlun Server 部署文档

本文档介绍如何将 kunlun-server-python 部署为 systemd 服务。建议使用专用系统用户运行，以提高安全性。

---

## 快速安装（推荐）

使用一键安装脚本：

```bash
bash <(curl -sL https://github.com/hochenggang/kunlun-server-python/raw/main/kunlun-server-python.sh) install
```

脚本会自动：
- 检测最新版本
- 下载并解压代码
- 创建专用用户和 systemd 服务
- 配置环境变量
- 启动服务

---

## 手动部署

### 1. 创建专用用户

```bash
useradd -r -s /usr/sbin/nologin -M kunlun-server-python
```

- `-r`：创建系统用户
- `-s /usr/sbin/nologin`：禁止登录
- `-M`：不创建 Home 目录

---

### 2. 下载代码

从 GitHub Releases 下载最新版本：

```bash
# 获取最新版本号
LATEST_VERSION=$(curl -sI https://github.com/hochenggang/kunlun-server-python/releases/latest | grep -i "location:" | sed 's/.*tag\///' | tr -d '\r\n')

# 创建目录
mkdir -p /opt/apps/kunlun-server-python
cd /opt/apps/kunlun-server-python

# 下载并解压
curl -sL https://github.com/hochenggang/kunlun-server-python/archive/refs/tags/${LATEST_VERSION}.tar.gz -o release.tar.gz
tar -xzf release.tar.gz
mv kunlun-server-python-*/* .
rm -rf kunlun-server-python-* release.tar.gz

# 记录版本号
echo $LATEST_VERSION > .version
```

---

### 3. 创建虚拟环境并安装依赖

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

### 4. 创建数据库目录

应用运行时会在 `db/` 目录下创建 SQLite 数据库文件：

```bash
mkdir -p db
```

---

### 5. 创建环境变量文件

创建 `.env` 文件配置管理员 Token：

```bash
cat > .env << 'EOF'
ADMIN_TOKEN=your_secure_token_here
EOF
```

**重要**：请将 `your_secure_token_here` 替换为强密码，用于访问 `/admin/*` API。

---

### 6. 设置目录权限

将应用目录所有者改为专用用户：

```bash
chown -R kunlun-server-python:kunlun-server-python /opt/apps/kunlun-server-python
chmod 600 /opt/apps/kunlun-server-python/.env
```

---

### 7. 创建 systemd 服务文件

```bash
nano /etc/systemd/system/kunlun-server-python.service
```

写入以下内容：

```ini
[Unit]
Description=Kunlun Server - Server Monitoring Backend
After=network.target

[Service]
User=kunlun-server-python
Group=kunlun-server-python
WorkingDirectory=/opt/apps/kunlun-server-python
Environment="PATH=/opt/apps/kunlun-server-python/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
EnvironmentFile=/opt/apps/kunlun-server-python/.env
ExecStart=/opt/apps/kunlun-server-python/venv/bin/python app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**配置说明**：
- `WorkingDirectory`：设置工作目录，确保数据库文件写入正确位置
- `Environment`：设置 PATH，确保能找到虚拟环境中的 Python
- `EnvironmentFile`：从 `.env` 文件加载环境变量（如 ADMIN_TOKEN）
- `ExecStart`：使用虚拟环境的 Python 执行应用
- `Restart=always`：服务退出时自动重启
- `RestartSec=5`：重启前等待 5 秒

---

### 8. 启动服务

```bash
# 重新加载 systemd 配置
systemctl daemon-reload

# 启动服务
systemctl start kunlun-server-python

# 设置开机自启
systemctl enable kunlun-server-python
```

---

### 9. 验证服务

```bash
# 查看服务状态
systemctl status kunlun-server-python

# 查看服务日志
journalctl -u kunlun-server-python -f

# 测试 API
curl http://localhost:8008/status
```

---

## 常用命令

```bash
# 重启服务
systemctl restart kunlun-server-python

# 停止服务
systemctl stop kunlun-server-python

# 查看最近 100 行日志
journalctl -u kunlun-server-python -n 100

# 查看今天的日志
journalctl -u kunlun-server-python --since today
```

---

## 版本升级

使用管理脚本升级：

```bash
# 升级到最新版本
kunlun-server-python.sh upgrade
```

或手动升级：

```bash
cd /opt/apps/kunlun-server-python

# 获取最新版本
LATEST_VERSION=$(curl -sI https://github.com/hochenggang/kunlun-server-python/releases/latest | grep -i "location:" | sed 's/.*tag\///' | tr -d '\r\n')

# 备份配置
cp .env .env.bak

# 下载新版本
curl -sL https://github.com/hochenggang/kunlun-server-python/archive/refs/tags/${LATEST_VERSION}.tar.gz -o release.tar.gz
tar -xzf release.tar.gz

# 更新文件
cp kunlun-server-python-*/app.py .
cp kunlun-server-python-*/requirements.txt .
rm -rf kunlun-server-python-* release.tar.gz

# 更新版本号
echo $LATEST_VERSION > .version

# 更新依赖
source venv/bin/activate
pip install -r requirements.txt

# 恢复配置
mv .env.bak .env

# 重启服务
systemctl restart kunlun-server-python
```

---

## 防火墙配置

如果服务器启用了防火墙，需要开放 8008 端口：

```bash
# firewalld
firewall-cmd --add-port=8008/tcp --permanent
firewall-cmd --reload

# ufw
ufw allow 8008/tcp

# iptables
iptables -A INPUT -p tcp --dport 8008 -j ACCEPT
```

---

## 反向代理配置（可选）

建议使用 Nginx 作为反向代理，并配置 HTTPS：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8008;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

---

## 故障排查

### 服务无法启动

1. 检查日志：`journalctl -u kunlun-server-python -n 50`
2. 检查文件权限：`ls -la /opt/apps/kunlun-server-python/`
3. 检查端口占用：`netstat -tlnp | grep 8008`

### 数据库写入失败

确保 `db/` 目录权限正确：

```bash
ls -la /opt/apps/kunlun-server-python/db/
# 如权限不正确，执行：
chown -R kunlun-server-python:kunlun-server-python /opt/apps/kunlun-server-python/db/
```

### Admin API 返回 401

检查 `.env` 文件中的 `ADMIN_TOKEN` 是否正确设置，请求时需在 Header 中携带：

```bash
curl -H "Authorization: your_token" http://localhost:8008/admin/client
```

---

## Docker 部署

### 使用 Docker 自行构建镜像部署

```bash
git clone https://github.com/hochenggang/kunlun-server-python.git
cd kunlun-server-python
```

### 使用 Docker 运行

确保已安装 Docker，然后运行以下命令：

```bash
mkdir -p /opt/kunlun-server/db
docker build -t kunlun-server:latest .
docker run -d --network host -e ADMIN_TOKEN=your_secure_token -v /opt/kunlun-server/db:/app/db -p 8008:8008 kunlun-server:latest
```

- `-e ADMIN_TOKEN=your_secure_token`：设置管理员鉴权 Token，用于访问 `/admin/*` API。**强烈建议设置一个强密码**，若不设置则默认为 `Admin123`。
- `-v /opt/kunlun-server/db:/app/db`：将主机的 `/opt/kunlun-server/db` 目录挂载到容器内的 `/app/db` 目录，用于持久化 SQLite 数据库文件。
- `-p 8008:8008`：访问主机的 8008 端口时，转发到容器的 8008 端口。若8008端口已经被使用，你可以修改`-p 宿主机端口:8008` 

---

### 访问 Web 界面

在浏览器中访问 `http://<server-ip>:8008`，即可查看服务器监控仪表盘。

---

### 删除节点

使用 Admin API 删除客户端及其所有关联数据：

```bash
# 删除客户端
curl -X DELETE -H "Authorization: {ADMIN_TOKEN}" http://localhost:8008/admin/client/{CLIENT_ID}
```

---

## Admin API 说明

服务端提供管理员 API，用于管理客户端：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/admin/client` | 获取所有客户端列表 |
| PUT | `/admin/client/{client_id}` | 更新客户端信息 |
| DELETE | `/admin/client/{client_id}` | 删除客户端及关联数据 |

所有 Admin API 需要在请求头中携带 `Authorization: <token>` 进行鉴权。

### 审核新客户端

新客户端首次上报时，`status=0`（待审核），需要管理员审核通过后才能正常入库数据：

```bash
# 查看待审核客户端列表
curl -H "Authorization: $ADMIN_TOKEN" http://localhost:8008/admin/client

# 审核通过（将 status 设为 1）
curl -X PUT -H "Authorization: $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": 1}' \
  http://localhost:8008/admin/client/1
```

---

## 管理脚本命令

安装后可使用管理脚本：

```bash
# 查看帮助
kunlun-server-python.sh help

# 服务管理
kunlun-server-python.sh status
kunlun-server-python.sh start
kunlun-server-python.sh stop
kunlun-server-python.sh restart
kunlun-server-python.sh logs

# 版本管理
kunlun-server-python.sh version
kunlun-server-python.sh upgrade

# 客户端管理
kunlun-server-python.sh client list
kunlun-server-python.sh client pending
kunlun-server-python.sh client approve <id>
kunlun-server-python.sh client reject <id>
kunlun-server-python.sh client delete <id>
```
