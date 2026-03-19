# Kunlun Server Monitoring

Kunlun Server Monitoring 是一个轻量级、高效的服务器监控系统，旨在帮助用户实时监控服务器的性能指标，并通过直观的 Web 界面展示数据。系统由 **Kunlun Server**（后端）和 **Kunlun Client**（客户端）组成，支持跨平台部署，适用于各种 Linux 环境。

---

## 功能特性

### **实时监控**
- 采集 CPU、内存、磁盘、网络等关键性能指标
- 支持多台服务器的集中监控
- 数据分级存储：秒级、分钟级、小时级

### **历史数据查询**
- 提供过去一段时间内的性能数据查询功能
- 支持数据采样和可视化展示

### **轻量高效**
- 后端基于 Python + FastAPI + SQLite，资源占用低
- 客户端基于 C 语言实现，性能优异

### **易于部署**
- 提供一键安装脚本，无需 git 依赖
- 支持自动版本检测和升级
- 提供 Docker 镜像，支持快速部署

### **跨平台支持**
- 兼容主流 Linux 发行版（Ubuntu、CentOS、Debian、Arch 等）

---

## 系统架构

Kunlun Server Monitoring 由以下组件组成：

1. **Kunlun Server**（后端）：
   - 基于 FastAPI 提供 RESTful API，用于接收和存储客户端上报的数据
   - 使用 SQLite 作为轻量级数据库，支持数据持久化
   - 提供 Web 界面，展示实时和历史监控数据

2. **Kunlun Client**（客户端）：
   - 基于 C 语言实现，实时采集服务器性能指标
   - 支持自定义上报地址和监测间隔
   - 通过 HTTP POST 请求将数据上报到 Kunlun Server

---

## 快速开始

### 部署 Kunlun Server

#### 一键安装（推荐）

```bash
bash <(curl -sL https://github.com/hochenggang/kunlun-server-python/raw/main/kunlun-server-python.sh) install
```

安装脚本会自动：
- 检测并下载最新版本
- 创建专用用户和 systemd 服务
- 配置环境变量
- 启动服务

#### 手动部署

详见 [部署文档](deploy.md)

---

### 部署 [Kunlun Client](https://github.com/hochenggang/kunlun)

#### 使用安装脚本

在需要监控的服务器上运行以下命令：

```bash
bash <(curl -sL https://github.com/hochenggang/kunlun/raw/refs/heads/main/kunlun-client-install.sh)
```

按 1 安装，输入上报地址（如 `http://<server-ip>:8008/status`）即可完成安装。

---

## 版本管理

### 查看当前版本

```bash
kunlun-server-python.sh version
```

### 升级到最新版本

```bash
kunlun-server-python.sh upgrade
```

升级脚本会：
- 自动检测最新版本
- 下载并更新代码
- 保留配置文件和数据库
- 自动重启服务

---

## 管理脚本命令

```bash
# 服务管理
kunlun-server-python.sh status      # 查看服务状态
kunlun-server-python.sh start       # 启动服务
kunlun-server-python.sh stop        # 停止服务
kunlun-server-python.sh restart     # 重启服务
kunlun-server-python.sh logs        # 查看日志

# 版本管理
kunlun-server-python.sh version     # 查看版本
kunlun-server-python.sh upgrade     # 升级版本

# 客户端管理
kunlun-server-python.sh client list           # 查看所有客户端
kunlun-server-python.sh client pending        # 查看待审核客户端
kunlun-server-python.sh client approve <id>   # 审核通过
kunlun-server-python.sh client reject <id>    # 拒绝客户端
kunlun-server-python.sh client delete <id>    # 删除客户端
```

---

## API 说明

### 数据查询 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/status` | 健康检查 |
| GET | `/status/latest` | 获取所有客户端最新状态 |
| GET | `/status/seconds?client_id=X` | 获取秒级数据 |
| GET | `/status/minutes?client_id=X` | 获取分钟级数据 |
| GET | `/status/hours?client_id=X` | 获取小时级数据 |

**响应格式**：表格模式（减少数据传输量）
```json
[
  ["timestamp", "cpu_user", "cpu_system", ...],
  [1234567890, 10.5, 5.2, ...],
  [1234567900, 12.3, 6.1, ...]
]
```

### Admin API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/admin/client` | 获取所有客户端列表 |
| PUT | `/admin/client/{id}` | 更新客户端信息 |
| DELETE | `/admin/client/{id}` | 删除客户端及关联数据 |

所有 Admin API 需要在请求头中携带 `Authorization: <token>` 进行鉴权。

---

## 发布流程

本项目使用 GitHub Actions 自动发布：

1. 创建并推送 tag：
   ```bash
   git tag v0.3.6
   git push origin v0.3.6
   ```

2. GitHub Actions 自动构建并发布 Release，包含：
   - 源码压缩包（tar.gz 和 zip）
   - 发布说明

3. 安装脚本自动检测最新版本进行安装/升级

---

## 贡献指南

欢迎提交 Issue 或 Pull Request 为 Kunlun Server Monitoring 贡献力量！

---

## 许可证

Kunlun Server Monitoring 基于 [MIT 许可证](https://opensource.org/licenses/MIT) 开源。

---

## 联系我们

如有问题或建议，请通过 GitHub Issues 联系我。

---

感谢使用 Kunlun Server Monitoring！
