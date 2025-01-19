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

#### 使用 Docker 部署

##### 克隆项目

```bash
git clone https://github.com/hochenggang/kunlun-server-python.git
cd kunlun-server-python
```

##### 使用 Docker 运行

确保已安装 Docker，然后运行以下命令：

```bash
mkdir -p /opt/kunlun-server/db
docker build -t kunlun-server .
docker run -v /opt/kunlun-server/db:/app/db -p 8008:8008 kunlun-server
```

- `-v /opt/kunlun-server/db:/app/db`：将主机的 `/opt/kunlun-server/db` 目录挂载到容器内的 `/app/db` 目录，用于持久化 SQLite 数据库文件。
- `-p 8008:8008`：将容器的 8008 端口映射到主机的 8008 端口。

##### 访问 Web 界面

在浏览器中访问 `http://localhost:8008`，即可查看服务器监控仪表盘。

---

### 2. 部署 Kunlun Client

#### 使用安装脚本

在需要监控的服务器上运行以下命令：

```bash
curl -L https://github.com/hochenggang/kunlun/raw/refs/heads/main/kunlun-client-install.sh -o kunlun-client-install.sh
chmod +x kunlun-client-install.sh
./kunlun-client-install.sh
```

按照提示输入监测间隔（秒）和上报地址（如 `http://<server-ip>:8008/status`）即可完成安装。

#### 查看服务状态

安装完成后，Kunlun Client 会自动启动。您可以使用以下命令查看服务状态：

```bash
systemctl status kunlun
```

---

## 数据采集与上报

Kunlun Client 采集的指标数据包括以下字段：

| 参数名               | 类型     | 说明                                                                 |
|----------------------|----------|----------------------------------------------------------------------|
| `machine_id`         | `char`   | Linux 服务器的 machine-id                                            |
| `uptime`             | `long`   | 系统运行时间（秒）。                                                |
| `load_1min`          | `double` | 系统 1 分钟负载。                                                   |
| `load_5min`          | `double` | 系统 5 分钟负载。                                                   |
| `load_15min`         | `double` | 系统 15 分钟负载。                                                  |
| `net_tx`             | `ulong`  | 默认路由接口的发送流量（字节）。                                    |
| `net_rx`             | `ulong`  | 默认路由接口的接收流量（字节）。                                    |
| `disk_delay`         | `long`   | 磁盘延迟（微秒）。                                                  |
| `cpu_delay`          | `long`   | CPU 延迟（微秒）。                                                  |
| `disks_total_kb`     | `ulong`  | 磁盘总容量（KB）。                                                  |
| `disks_avail_kb`     | `ulong`  | 磁盘可用容量（KB）。                                                |
| `tcp_connections`    | `int`    | TCP 连接数。                                                        |
| `udp_connections`    | `int`    | UDP 连接数。                                                        |
| `cpu_num_cores`      | `int`    | CPU 核心数。                                                        |
| `task_total`         | `int`    | 总任务数。                                                          |
| `task_running`       | `int`    | 正在运行的任务数。                                                  |
| `cpu_us`             | `double` | 用户空间占用 CPU 时间累计值。                                      |
| `cpu_sy`             | `double` | 内核空间占用 CPU 时间累计值。                                      |
| `cpu_ni`             | `double` | 用户进程空间内改变过优先级的进程占用 CPU 时间累计值。              |
| `cpu_id`             | `double` | 空闲 CPU 时间累计值。                                              |
| `cpu_wa`             | `double` | 等待 I/O 的 CPU 时间累计值。                                       |
| `cpu_hi`             | `double` | 硬件中断占用 CPU 时间累计值。                                      |
| `cpu_st`             | `double` | 虚拟机偷取的 CPU 时间累计值。                                      |
| `mem_total`          | `double` | 总内存大小（MiB）。                                                 |
| `mem_free`           | `double` | 空闲内存大小（MiB）。                                               |
| `mem_used`           | `double` | 已用内存大小（MiB）。                                               |
| `mem_buff_cache`     | `double` | 缓存和缓冲区内存大小（MiB）。                                       |

---

## 配置说明

### 1. 监测间隔
监测间隔是指 Kunlun Client 采集系统指标并上报的时间间隔（单位：秒）。默认值为 10 秒。

### 2. 上报地址
上报地址是指 Kunlun Client 将采集到的指标数据发送到的 HTTP 地址。例如：`http://<server-ip>:8008/status`。

### 3. 服务配置
Kunlun Client 的 systemd 服务配置文件位于 `/etc/systemd/system/kunlun.service`，内容如下：

```ini
[Unit]
Description=Kunlun System Monitor
After=network.target

[Service]
ExecStart=/usr/local/bin/kunlun-client -s 10 -u http://<server-ip>:8008/status
Restart=always
User=root

[Install]
WantedBy=multi-user.target
```

---

## 从源码构建

### 1. 克隆仓库

```bash
git clone https://github.com/hochenggang/kunlun.git
cd kunlun
```

### 2. 编译 Kunlun Client

使用 `gcc` 编译 Kunlun Client：

```bash
gcc -o kunlun-client kunlun-client.c
```

---

## 常见问题

### 1. 上报地址校验失败
确保上报地址返回的内容包含 `kunlun`。例如，可以在服务器上创建一个简单的 HTTP 服务，返回 `kunlun`。

### 2. 服务启动失败
检查 `/etc/systemd/system/kunlun.service` 文件中的路径和参数是否正确，确保 Kunlun Client 二进制文件存在且可执行。

### 3. 如何修改监测间隔或上报地址
修改 `/etc/systemd/system/kunlun.service` 文件中的 `ExecStart` 参数，然后重启服务：

```bash
sudo systemctl daemon-reload
sudo systemctl restart kunlun
```

---

## 贡献指南

欢迎提交 Issue 或 Pull Request 为 Kunlun Server Monitoring 贡献力量！

---

## 许可证

Kunlun Server Monitoring 基于 [MIT 许可证](https://opensource.org/licenses/MIT) 开源。

---

## 联系我们

如有问题或建议，请通过 GitHub Issues 联系我们。

---

感谢使用 Kunlun Server Monitoring！