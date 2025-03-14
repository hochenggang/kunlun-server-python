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

### 1. 部署 Kunlun Server


#### 使用 Docker 拉取镜像部署 （更快捷）

```bash
docker pull hochenggang/kunlun-server:0.1.0
mkdir -p /opt/kunlun-server/db
docker run -d --network host -v /opt/kunlun-server/db:/app/db -p 8008:8008 hochenggang/kunlun-server:0.1.0

```

- `-v /opt/kunlun-server/db:/app/db`：将主机的 `/opt/kunlun-server/db` 目录挂载到容器内的 `/app/db` 目录，用于持久化 SQLite 数据库文件。
- `-p 8008:8008`：访问主机的 8008 端口时，转发到容器的 8008 端口。若8008端口已经被使用，你可以修改`-p 宿主机端口:8008` 


#### 使用 Docker 自行构建镜像部署 （更安全）

##### 克隆项目

```bash
git clone https://github.com/hochenggang/kunlun-server-python.git
cd kunlun-server-python
```

##### 使用 Docker 运行

确保已安装 Docker，然后运行以下命令：

```bash
mkdir -p /opt/kunlun-server/db
docker build -t kunlun-server:0.1.0 .
docker run -d --network host -v /opt/kunlun-server/db:/app/db -p 8008:8008 kunlun-server:0.1.0
```



##### 访问 Web 界面

在浏览器中访问 `http://<server-ip>:8008`，即可查看服务器监控仪表盘。
为了增强安全性和性能，可以使用 Nginx 作为反向代理，并通过 Cloudflare 配置 SSL。

注意：目前这个版本的 Server 仅为 Demo 版本，极简化设计、没有鉴权和认证，不建议公开分享，避免被打爆，请勿用于生产环境。或许，你可以自行开发更好的 Server

---

### 2. 部署 [Kunlun Client](https://github.com/hochenggang/kunlun)

#### 使用安装脚本

在需要监控的服务器上运行以下命令：

```bash
curl -L https://github.com/hochenggang/kunlun/raw/refs/heads/main/kunlun-client-install.sh -o kunlun-client-install.sh
chmod +x kunlun-client-install.sh
./kunlun-client-install.sh
```

按照提示输入上报地址（如 `http://<server-ip>:8008/status`）即可完成安装。



安装完成后，Kunlun Client 会自动启动。您可以使用以下命令查看服务状态：

```bash
systemctl status kunlun
```

---
#### 自行拉取源码编译


```bash
git clone https://github.com/hochenggang/kunlun.git
cd kunlun
```

使用 `gcc` 编译 Kunlun Client：

```bash
gcc -o kunlun-client kunlun-client.c
```


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