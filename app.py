import time
import logging
import sqlite3
from typing import List, Any

from fastapi import FastAPI, Request, HTTPException, Form, Response, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# SQLite 数据库文件路径
DATABASE = "db/kunlun.db"


# 初始化数据库
def init_db():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        # 启用 WAL 模式
        cursor.execute("PRAGMA journal_mode=WAL;")
        # 设置 busy_timeout 为 10 秒
        cursor.execute("PRAGMA busy_timeout=10000;")
        # 创建表，并添加字段备注
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS client (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_id TEXT NOT NULL UNIQUE,  -- 使用 machine_id 作为唯一性检测
                name TEXT  -- 客户端名称（未来允许用户更新）
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL, -- 外键，引用 client 表的 id
                insert_utc_ts INTEGER NOT NULL, -- 数据插入时间（UTC 时间戳）
                uptime INTEGER, -- 系统已运行的时间（秒）
                load_1min REAL, -- 过去 1 分钟的平均负载
                load_5min REAL, -- 过去 5 分钟的平均负载
                load_15min REAL, -- 过去 15 分钟的平均负载
                net_tx INTEGER, -- 默认路由接口的发送流量（字节）
                net_rx INTEGER, -- 默认路由接口的接收流量（字节）
                disk_delay INTEGER, -- 磁盘延迟（微秒）
                cpu_delay INTEGER, -- CPU 延迟（微秒）
                disks_total_kb INTEGER, -- 磁盘总容量（KB）
                disks_avail_kb INTEGER, -- 磁盘可用容量（KB）
                tcp_connections INTEGER, -- TCP 连接数
                udp_connections INTEGER, -- UDP 连接数
                cpu_num_cores INTEGER, -- CPU 核心数
                task_total INTEGER, -- 总任务数
                task_running INTEGER, -- 正在运行的任务数
                cpu_us REAL, -- 用户空间占用 CPU 累计统计值
                cpu_sy REAL, -- 内核空间占用 CPU 累计统计值
                cpu_ni REAL, -- 用户进程空间内改变过优先级的进程占用 CPU 累计统计值
                cpu_id REAL, -- 空闲 CPU 累计统计值
                cpu_wa REAL, -- 等待 I/O 的 CPU 累计统计值
                cpu_hi REAL, -- 硬件中断占用 CPU 累计统计值
                cpu_st REAL, -- 虚拟机偷取的 CPU 累计统计值
                mem_total REAL, -- 总内存大小（MiB）
                mem_free REAL, -- 空闲内存大小（MiB）
                mem_used REAL, -- 已用内存大小（MiB）
                mem_buff_cache REAL, -- 缓存和缓冲区内存大小（MiB）
                FOREIGN KEY (client_id) REFERENCES client(id) -- 外键约束
            );
        """)

        # 创建复合索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_client_id_time
            ON status (client_id, insert_utc_ts)
        """)
        conn.commit()


def save_client_row(machine_id: str, name: str = None) -> int:
    """
    尝试插入 machine_id 并返回 client_id
    """
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        # 查询已有 id
        cursor.execute("SELECT id FROM client WHERE machine_id = ?;", (machine_id,))
        result = cursor.fetchone()

        if result:
            # 如果记录已存在，返回已有 id
            return result[0]
        else:
            # 如果记录不存在，插入新记录并返回新 id
            cursor.execute(
                "INSERT INTO client (machine_id, name) VALUES (?, ?);",
                (machine_id, name),
            )
            conn.commit()
            return cursor.lastrowid  # 返回新插入的 id


def save_status_row(row: List[Any]):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO status (
                client_id, insert_utc_ts, uptime, load_1min, load_5min, load_15min,
                net_tx, net_rx, disk_delay, cpu_delay, disks_total_kb, disks_avail_kb,
                tcp_connections, udp_connections, cpu_num_cores, task_total, task_running,
                cpu_us, cpu_sy, cpu_ni, cpu_id, cpu_wa, cpu_hi, cpu_st, mem_total, mem_free, mem_used, mem_buff_cache
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            row,
        )
        conn.commit()


def get_latest_status_data() -> List[sqlite3.Row]:
    """
    查询数据库中，以 machine_id 分组的 insert_utc_ts 最新一行数据
    """
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute("""
            SELECT 
                c.machine_id, c.name, s.*
            FROM (
                SELECT 
                    *, 
                    ROW_NUMBER() OVER (PARTITION BY client_id ORDER BY insert_utc_ts DESC) AS rn
                FROM 
                    status
            ) s
            JOIN 
                client c ON s.client_id = c.id
            WHERE 
                s.rn = 1;
            """)
        return cursor.fetchall()


def get_history_data(
    client_id: int, seconds: int, columns: List[str]
) -> List[List[Any]]:
    """
    获取某个 client_id 过去 seconds 秒内的指定列数据记录。
    如果某个列的数据量大于 60，均匀采样出 60 条数据。
    """
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.row_factory = sqlite3.Row

        # 计算时间范围
        current_time = int(time.time())
        start_time = current_time - seconds

        # 查询指定时间范围内的数据
        query = f"""
            SELECT {", ".join(columns)}, insert_utc_ts
            FROM status
            WHERE client_id = ? AND insert_utc_ts >= ?
            ORDER BY insert_utc_ts ASC;
        """
        cursor.execute(query, (client_id, start_time))
        rows = cursor.fetchall()

        if not rows:
            return []

        # 将数据按列分组
        column_data = {col: [] for col in columns}
        for row in rows:
            for col in columns:
                column_data[col].append(row[col])

        # 对每个列的数据进行采样
        sampled_data = []
        for col in columns:
            data = column_data[col]
            if len(data) > 60:
                # 均匀采样 60 条数据
                step = len(data) / 60
                sampled_data.append([data[int(i * step)] for i in range(60)])
            else:
                # 不足 60 条，返回全部数据
                sampled_data.append(data)

        return sampled_data


# 初始化 FastAPI 应用
app = FastAPI()

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 全局错误处理器
@app.exception_handler(Exception)
async def handle_exception(request: Request, exc: Exception):
    """
    捕获所有异常并返回 500 错误
    """
    logger.error(f"An error occurred: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": str(exc)},
    )


@app.post("/")
async def route_post_index_test(request: Request):
    """
    测试接收监控数据并返回
    """
    # 解析表单数据
    form_data = await request.form()
    form_dict = dict(form_data)

    # 返回客户端 IP 和表单数据
    return {**form_dict}


@app.post("/status")
async def route_post_status(
    machine_id: str = Form(...),
    uptime: int = Form(...),
    load_1min: float = Form(...),
    load_5min: float = Form(...),
    load_15min: float = Form(...),
    net_tx: int = Form(...),
    net_rx: int = Form(...),
    disk_delay: int = Form(...),
    cpu_delay: int = Form(...),
    disks_total_kb: int = Form(...),
    disks_avail_kb: int = Form(...),
    tcp_connections: int = Form(...),
    udp_connections: int = Form(...),
    cpu_num_cores: int = Form(...),
    task_total: int = Form(...),
    task_running: int = Form(...),
    cpu_us: float = Form(...),
    cpu_sy: float = Form(...),
    cpu_ni: float = Form(...),
    cpu_id: float = Form(...),
    cpu_wa: float = Form(...),
    cpu_hi: float = Form(...),
    cpu_st: float = Form(...),
    mem_total: float = Form(...),
    mem_free: float = Form(...),
    mem_used: float = Form(...),
    mem_buff_cache: float = Form(...),
):
    """
    接收监控数据并保存到数据库
    """
    # 获取或创建客户端记录
    client_id = save_client_row(machine_id)

    try:
        row = (
            client_id,
            round(time.time()),  # insert_utc_ts
            uptime,
            load_1min,
            load_5min,
            load_15min,
            net_tx,
            net_rx,
            disk_delay,
            cpu_delay,
            disks_total_kb,
            disks_avail_kb,
            tcp_connections,
            udp_connections,
            cpu_num_cores,
            task_total,
            task_running,
            cpu_us,
            cpu_sy,
            cpu_ni,
            cpu_id,
            cpu_wa,
            cpu_hi,
            cpu_st,
            mem_total,
            mem_free,
            mem_used,
            mem_buff_cache,
        )
        # 保存数据到数据库
        save_status_row(row)
        return {"status": "ok", "client_id": client_id}

    except Exception as e:
        logger.warning(f"Failed to save status: {e} machine_id:{machine_id}")
        # 未来加上黑名单机制，如果提交了异常数据，视为攻击行为
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/")
async def route_get_index():
    with open("./kunlun.html", "rt", encoding="utf-8") as html:
        return Response(content=html.read(), media_type="text/html")


@app.get("/status")
async def route_get_status():
    return Response(content="kunlun", media_type="text/plain")


@app.get("/status/latest")
async def route_get_latest_status():
    """
    查询数据库中，以 client_ip 分组的 insert_utc_ts 最新一行数据
    """
    rows = get_latest_status_data()
    return [dict(r) for r in rows]


@app.get("/status/{client_id}/history")
async def route_get_client_history(
    client_id: int,
    columns: str = Query(..., description="需要查询的列，以逗号分隔"),
    seconds: int = Query(..., description="查询过去多少秒的数据"),
):
    """
    获取某个 client_id 过去 seconds 秒内的指定列数据记录。
    如果某个列的数据量大于 30，均匀采样出 30 条数据。
    """
    try:
        # 解析 columns 参数
        columns_list = [col.strip() for col in columns.split(",")]

        # 获取历史数据
        history_data = get_history_data(client_id, seconds, columns_list)

        # 返回结果
        return {"client_id": client_id, "data": history_data}
    except Exception as e:
        logger.error(f"Failed to fetch history data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    init_db()
    uvicorn.run(app, host="::", port=8008)
