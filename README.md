# Kunlun Server Monitoring

Kunlun Server Monitoring 是一个轻量级、高效的服务器监控系统，旨在帮助用户实时监控服务器的性能指标，并通过直观的 Web 界面展示数据。系统由 **Kunlun Server**（后端）和 **Kunlun Client**（客户端）组成，支持跨平台部署，适用于各种 Linux 环境。

---

## 功能特性

### **实时监控**
- 采集 CPU、内存、磁盘、网络等关键性能指标。
- 支持多台服务器的集中监控。

### **历史数据查询**
- 提供过去一段时间内的性能数据查询功能。
- 支持数据采样和可视化展示。

### **轻量高效**
- 后端基于 Python + FastAPI + SQLite，资源占用低。
- 客户端基于 C 语言实现，性能优异。

### **易于部署**
- 提供 Docker 镜像，支持快速部署。
- 客户端支持一键安装脚本和 systemd 守护进程。

### **跨平台支持**
- 兼容主流 Linux 发行版（Ubuntu、CentOS、Debian、Arch 等）。

---

## 系统架构

Kunlun Server Monitoring 由以下组件组成：

1. **Kunlun Server**（后端）：
   - 基于 FastAPI 提供 RESTful API，用于接收和存储客户端上报的数据。
   - 使用 SQLite 作为轻量级数据库，支持数据持久化。
   - 提供 Web 界面，展示实时和历史监控数据。

2. **Kunlun Client**（客户端）：
   - 基于 C 语言实现，实时采集服务器性能指标。
   - 支持自定义上报地址和监测间隔。
   - 通过 HTTP POST 请求将数据上报到 Kunlun Server。

---

## 快速开始

### 部署 Kunlun Server

#### 本地部署
[部署文档](deploy.md)
或通过一键部署脚本
```bash
bash <(curl -sL https://github.com/hochenggang/kunlun-server-python/raw/refs/heads/main/kunlun-server-python.sh) install
```



---

### 部署 [Kunlun Client](https://github.com/hochenggang/kunlun)

#### 使用安装脚本

在需要监控的服务器上运行以下命令：

```bash
bash <(curl -sL https://github.com/hochenggang/kunlun/raw/refs/heads/main/kunlun-client-install.sh)
```

按 1 安装，输入上报地址（如 `http://<server-ip>:8008/status`）即可完成安装。

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