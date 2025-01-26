import os
import logging
import sqlite3
from typing import Optional

from pydantic import BaseModel
from fastapi import FastAPI, Form, Response, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# 初始化日志

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


# 初始化数据库
os.makedirs("db", exist_ok=True)
DATABASE = "db/kunlun_status.db"


def init_db():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        # 启用 WAL 模式
        cursor.execute("PRAGMA journal_mode=WAL;")
        # 设置 busy_timeout 为 10 秒
        cursor.execute("PRAGMA busy_timeout=10000;")
        # 创建 client 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS client (
                id INTEGER PRIMARY KEY NOT NULL,
                machine_id TEXT UNIQUE NOT NULL,
                hostname TEXT NOT NULL
            )
        """)

        columns = """
            timestamp INTEGER NOT NULL,
            uptime_s INTEGER NOT NULL,
            load_1min REAL NOT NULL,
            load_5min REAL NOT NULL,
            load_15min REAL NOT NULL,
            running_tasks INTEGER NOT NULL,
            total_tasks INTEGER NOT NULL,
            cpu_user REAL NOT NULL,
            cpu_system REAL NOT NULL,
            cpu_nice REAL NOT NULL,
            cpu_idle REAL NOT NULL,
            cpu_iowait REAL NOT NULL,
            cpu_irq REAL NOT NULL,
            cpu_softirq REAL NOT NULL,
            cpu_steal REAL NOT NULL,
            mem_total_mib REAL NOT NULL,
            mem_free_mib REAL NOT NULL,
            mem_used_mib REAL NOT NULL,
            mem_buff_cache_mib REAL NOT NULL,
            tcp_connections INTEGER NOT NULL,
            udp_connections INTEGER NOT NULL,
            default_interface_net_rx_bytes INTEGER NOT NULL,
            default_interface_net_tx_bytes INTEGER NOT NULL,
            cpu_num_cores INTEGER NOT NULL,
            cpu_delay_us INTEGER NOT NULL,
            disk_delay_us INTEGER NOT NULL,
            root_disk_total_kb INTEGER NOT NULL,
            root_disk_avail_kb INTEGER NOT NULL,
            reads_completed INTEGER NOT NULL,
            writes_completed INTEGER NOT NULL,
            reading_ms INTEGER NOT NULL,
            writing_ms INTEGER NOT NULL,
            iotime_ms INTEGER NOT NULL,
            ios_in_progress INTEGER NOT NULL,
            weighted_io_time INTEGER NOT NULL
        """
        # 创建 status_latest 表
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS status_latest (
                client_id INTEGER PRIMARY KEY,
                {columns},
                FOREIGN KEY (client_id) REFERENCES client(id)
            )
        """)
        # 创建 status_seconds 表
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS status_seconds (
                client_id INTEGER NOT NULL,
                {columns},
                PRIMARY KEY (client_id, timestamp),
                FOREIGN KEY (client_id) REFERENCES client(id)
            )
        """)
        # 创建 status_minutes 表
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS status_minutes (
                client_id INTEGER NOT NULL,
                {columns},
                PRIMARY KEY (client_id, timestamp),
                FOREIGN KEY (client_id) REFERENCES client(id)
            )
        """)
        # 创建 status_hours 表
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS status_hours (
                client_id INTEGER NOT NULL,
                {columns},
                PRIMARY KEY (client_id, timestamp),
                FOREIGN KEY (client_id) REFERENCES client(id)
            )
        """)
        conn.commit()


init_db()


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


# 定义数据类型
class KunlunReportLine(BaseModel):
    client_id: Optional[int] = None
    timestamp: int
    uptime_s: int
    load_1min: float
    load_5min: float
    load_15min: float
    running_tasks: int
    total_tasks: int
    cpu_user: float
    cpu_system: float
    cpu_nice: float
    cpu_idle: float
    cpu_iowait: float
    cpu_irq: float
    cpu_softirq: float
    cpu_steal: float
    mem_total_mib: float
    mem_free_mib: float
    mem_used_mib: float
    mem_buff_cache_mib: float
    tcp_connections: int
    udp_connections: int
    default_interface_net_rx_bytes: int
    default_interface_net_tx_bytes: int
    cpu_num_cores: int
    cpu_delay_us: int
    disk_delay_us: int
    root_disk_total_kb: int
    root_disk_avail_kb: int
    reads_completed: int
    writes_completed: int
    reading_ms: int
    writing_ms: int
    iotime_ms: int
    ios_in_progress: int
    weighted_io_time: int
    machine_id: Optional[str] = None
    hostname: Optional[str] = "unknown"


# 这是需要的字段名称列表
FIELDS_LIST = [
    "timestamp",
    "uptime_s",
    "load_1min",
    "load_5min",
    "load_15min",
    "running_tasks",
    "total_tasks",
    "cpu_user",
    "cpu_system",
    "cpu_nice",
    "cpu_idle",
    "cpu_iowait",
    "cpu_irq",
    "cpu_softirq",
    "cpu_steal",
    "mem_total_mib",
    "mem_free_mib",
    "mem_used_mib",
    "mem_buff_cache_mib",
    "tcp_connections",
    "udp_connections",
    "default_interface_net_rx_bytes",
    "default_interface_net_tx_bytes",
    "cpu_num_cores",
    "cpu_delay_us",
    "disk_delay_us",
    "root_disk_total_kb",
    "root_disk_avail_kb",
    "reads_completed",
    "writes_completed",
    "reading_ms",
    "writing_ms",
    "iotime_ms",
    "ios_in_progress",
    "weighted_io_time",
    "machine_id",
    "hostname",
]


# 动态生成 SQL 查询
def generate_insert_query(table_name: str, fields: list) -> str:
    """
    生成 INSERT OR REPLACE 查询语句。

    :param table_name: 表名
    :param fields: 字段列表
    :return: 生成的 SQL 查询语句
    """
    # 生成字段部分
    fields_str = ", ".join(fields)
    # 生成占位符部分
    placeholders = ", ".join(["?"] * len(fields))
    # 返回完整的 SQL 查询
    return f"INSERT OR REPLACE INTO {table_name} ({fields_str}) VALUES ({placeholders})"


# 定义路由


def db_get_client_id(machine_id: str, hostname: str) -> int:
    """
    使用 machine_id 和 hostname 获取 client_id。
    如果 machine_id 不存在，则插入新记录并返回 client_id。
    如果 hostname 发生变化，则更新数据库中的 hostname。

    :param machine_id: 客户端的唯一标识
    :param hostname: 客户端的主机名
    :return: client_id
    """
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.row_factory = sqlite3.Row  # 将查询结果转换为字典

        # 查询 client 表
        cursor.execute(
            "SELECT id, hostname FROM client WHERE machine_id = ?", (machine_id,)
        )
        client = cursor.fetchone()

        if client is None:
            # 如果 machine_id 不存在，插入新记录
            # 查询当前最大 id
            cursor.execute("SELECT MAX(id) AS max_id FROM client")
            max_id_result = cursor.fetchone()
            new_id = (
                1 if max_id_result["max_id"] is None else max_id_result["max_id"] + 1
            )

            # 插入新记录
            cursor.execute(
                "INSERT INTO client (id, machine_id, hostname) VALUES (?, ?, ?)",
                (new_id, machine_id, hostname),
            )
            client_id = new_id
            logger.info(
                f"New client inserted: machine_id={machine_id}, client_id={client_id}"
            )
        else:
            # 如果 machine_id 存在，检查 hostname 是否需要更新
            client_id = client["id"]
            if client["hostname"] != hostname:
                cursor.execute(
                    "UPDATE client SET hostname = ? WHERE id = ?",
                    (hostname, client_id),
                )
                logger.info(
                    f"Hostname updated: client_id={client_id}, new_hostname={hostname}"
                )

        conn.commit()  # 提交事务
        return client_id


# 辅助函数


def hleper_calculate_delta(
    new_data: KunlunReportLine, last_data: KunlunReportLine
) -> KunlunReportLine:
    """
    计算两个 KunlunReportLine 对象之间的差值。

    :param new_data: 新的数据点
    :param last_data: 上一个数据点
    :return: 差值计算结果
    """
    delta_data = KunlunReportLine(
        client_id=new_data.client_id,
        timestamp=new_data.timestamp,
        uptime_s=new_data.uptime_s,
        load_1min=new_data.load_1min,
        load_5min=new_data.load_5min,
        load_15min=new_data.load_15min,
        running_tasks=new_data.running_tasks,
        total_tasks=new_data.total_tasks,
        cpu_user=new_data.cpu_user - last_data.cpu_user,
        cpu_system=new_data.cpu_system - last_data.cpu_system,
        cpu_nice=new_data.cpu_nice - last_data.cpu_nice,
        cpu_idle=new_data.cpu_idle - last_data.cpu_idle,
        cpu_iowait=new_data.cpu_iowait - last_data.cpu_iowait,
        cpu_irq=new_data.cpu_irq - last_data.cpu_irq,
        cpu_softirq=new_data.cpu_softirq - last_data.cpu_softirq,
        cpu_steal=new_data.cpu_steal - last_data.cpu_steal,
        mem_total_mib=new_data.mem_total_mib,
        mem_free_mib=new_data.mem_free_mib,
        mem_used_mib=new_data.mem_used_mib,
        mem_buff_cache_mib=new_data.mem_buff_cache_mib,
        tcp_connections=new_data.tcp_connections,
        udp_connections=new_data.udp_connections,
        default_interface_net_rx_bytes=new_data.default_interface_net_rx_bytes
        - last_data.default_interface_net_rx_bytes,
        default_interface_net_tx_bytes=new_data.default_interface_net_tx_bytes
        - last_data.default_interface_net_tx_bytes,
        cpu_num_cores=new_data.cpu_num_cores,
        cpu_delay_us=new_data.cpu_delay_us,
        disk_delay_us=new_data.disk_delay_us,
        root_disk_total_kb=new_data.root_disk_total_kb,
        root_disk_avail_kb=new_data.root_disk_avail_kb,
        reads_completed=new_data.reads_completed - last_data.reads_completed,
        writes_completed=new_data.writes_completed - last_data.writes_completed,
        reading_ms=new_data.reading_ms - last_data.reading_ms,
        writing_ms=new_data.writing_ms - last_data.writing_ms,
        iotime_ms=new_data.iotime_ms - last_data.iotime_ms,
        ios_in_progress=new_data.ios_in_progress,
        weighted_io_time=new_data.weighted_io_time - last_data.weighted_io_time,
        machine_id=new_data.machine_id,
        hostname=new_data.hostname,
    )
    return delta_data


# 自定义中间件
@app.middleware("http")
async def global_error_handler(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        return Response(
            status_code=400,
            content=f"{str(e)}",
            media_type="text/plain",
        )


@app.post("/status")
async def route_post_status(
    values: str = Form(...),
):
    """
    接收监控数据并保存到数据库
    """

    # 这是客户端传过来的数据
    values_list = values.split(",")

    # 进行简单校验
    if len(values_list) != len(FIELDS_LIST):
        return JSONResponse(
            status_code=400,
            content={
                "error": f"required fields {len(FIELDS_LIST)}, recived {len(values_list)} "
            },
        )

    kunlun_report_line = KunlunReportLine(
        **{FIELDS_LIST[i]: values_list[i] for i in range(len(FIELDS_LIST))}
    )
    if kunlun_report_line.timestamp % 10 != 0:
        return JSONResponse(
            status_code=400,
            content={
                "error": f"required timestamp must % 10 = 0, recived timestamp {kunlun_report_line.timestamp} % 10 = {kunlun_report_line.timestamp % 10} "
            },
        )

    # 获取 client_id
    client_id = db_get_client_id(
        kunlun_report_line.machine_id, kunlun_report_line.hostname
    )
    kunlun_report_line.client_id = client_id

    # 查询前一条最新数据, 为计算差值做准备
    kunlun_report_line_before = None
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute("SELECT * FROM status_latest WHERE client_id = ?", (client_id,))
        last_data = cursor.fetchone()
        if last_data:
            kunlun_report_line_before = KunlunReportLine(**last_data)

    # 写入最新状态
    kunlun_report_line_dict = kunlun_report_line.model_dump()
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            generate_insert_query(
                "status_latest", list(kunlun_report_line_dict.keys())[:-2]
            ),
            list(kunlun_report_line_dict.values())[:-2],
        )
        conn.commit()

    if not kunlun_report_line_before:
        return JSONResponse(status_code=200, content={"ok": 1})

    # 如果前一条最新原始数据存在，求取差值并写入十秒级汇总数据
    kunlun_report_line_delta_10s = hleper_calculate_delta(
        kunlun_report_line, kunlun_report_line_before
    )
    kunlun_report_line_delta_10s_dict = kunlun_report_line_delta_10s.model_dump()
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            generate_insert_query(
                "status_seconds", list(kunlun_report_line_delta_10s_dict.keys())[:-2]
            ),
            list(kunlun_report_line_delta_10s_dict.values())[:-2],
        )

        # 秒级数据只保留 1小时的数据，合计360条，需要清理超出上限的秒级数据
        cursor.execute(
            """
            DELETE FROM status_seconds
            WHERE (client_id, timestamp) IN (
                SELECT client_id, timestamp FROM status_seconds
                WHERE client_id = ? ORDER BY timestamp DESC LIMIT -1 OFFSET 360
            );
            """,  # 按时间戳降序，跳过最新360条，删除剩余旧数据
            (client_id,),
        )
        conn.commit()

    # 检查是否为每分钟的开始
    if kunlun_report_line.timestamp % 60 == 0:
        # logger.info(
        #     f"It's the start of a minute, calculating delta... {str(kunlun_report_line)}"
        # )

        # 汇总秒级数据，生成分钟级数据
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO status_minutes (
                    client_id, timestamp, uptime_s, load_1min, load_5min, load_15min,
                    running_tasks, total_tasks, cpu_user, cpu_system, cpu_nice, cpu_idle,
                    cpu_iowait, cpu_irq, cpu_softirq, cpu_steal, mem_total_mib, mem_free_mib,
                    mem_used_mib, mem_buff_cache_mib, tcp_connections, udp_connections,
                    default_interface_net_rx_bytes, default_interface_net_tx_bytes,
                    cpu_num_cores, cpu_delay_us, disk_delay_us,
                    root_disk_total_kb, root_disk_avail_kb, reads_completed, writes_completed,
                    reading_ms, writing_ms, iotime_ms, ios_in_progress, weighted_io_time
                )
                SELECT
                    client_id,
                    MAX(timestamp),
                    ROUND(AVG(uptime_s), 2),
                    ROUND(AVG(load_1min), 2), ROUND(AVG(load_5min), 2), ROUND(AVG(load_15min), 2),
                    ROUND(AVG(running_tasks), 2), ROUND(AVG(total_tasks), 2),
                    ROUND(SUM(cpu_user), 2), ROUND(SUM(cpu_system), 2), ROUND(SUM(cpu_nice), 2),
                    ROUND(SUM(cpu_idle), 2), ROUND(SUM(cpu_iowait), 2), ROUND(SUM(cpu_irq), 2), ROUND(SUM(cpu_softirq), 2), ROUND(SUM(cpu_steal), 2),
                    ROUND(AVG(mem_total_mib), 2), ROUND(AVG(mem_free_mib), 2), ROUND(AVG(mem_used_mib), 2), ROUND(AVG(mem_buff_cache_mib), 2),
                    ROUND(AVG(tcp_connections), 2), ROUND(AVG(udp_connections), 2),
                    SUM(default_interface_net_rx_bytes), SUM(default_interface_net_tx_bytes),
                    ROUND(AVG(cpu_num_cores), 2), ROUND(AVG(cpu_delay_us), 2), ROUND(AVG(disk_delay_us), 2),
                    ROUND(AVG(root_disk_total_kb), 2), ROUND(AVG(root_disk_avail_kb), 2),
                    SUM(reads_completed), SUM(writes_completed),
                    SUM(reading_ms), SUM(writing_ms), SUM(iotime_ms),
                    ROUND(AVG(ios_in_progress), 2), ROUND(SUM(weighted_io_time), 2)
                FROM status_seconds
                WHERE 
                    client_id = ? 
                    AND timestamp >= ? - 60
                GROUP BY client_id;
            """,
                (client_id, kunlun_report_line.timestamp),
            )

            # 清理超出上限的分钟级数据
            cursor.execute(
                """
                DELETE FROM status_minutes
                WHERE (client_id, timestamp) IN (
                    SELECT client_id, timestamp FROM status_minutes
                    WHERE client_id = ? ORDER BY timestamp DESC LIMIT -1  OFFSET 1440
                );
            """,  # 保留最新1440条（24小时）
                (client_id,),
            )
            conn.commit()

    # 检查是否为每小时的开始
    if kunlun_report_line.timestamp % 3600 == 0:
        # logger.info(
        #     f"It's the start of a hour, calculating delta... {str(kunlun_report_line)}"
        # )
        # 汇总分钟级数据，生成小时级数据
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO status_hours (
                    client_id, timestamp, uptime_s, load_1min, load_5min, load_15min,
                    running_tasks, total_tasks, cpu_user, cpu_system, cpu_nice, cpu_idle,
                    cpu_iowait, cpu_irq, cpu_softirq, cpu_steal, mem_total_mib, mem_free_mib,
                    mem_used_mib, mem_buff_cache_mib, tcp_connections, udp_connections,
                    default_interface_net_rx_bytes, default_interface_net_tx_bytes,
                    cpu_num_cores, cpu_delay_us, disk_delay_us,
                    root_disk_total_kb, root_disk_avail_kb, reads_completed, writes_completed,
                    reading_ms, writing_ms, iotime_ms, ios_in_progress, weighted_io_time
                )
                SELECT
                    client_id,
                    MAX(timestamp),
                    ROUND(AVG(uptime_s), 2),
                    ROUND(AVG(load_1min), 2), ROUND(AVG(load_5min), 2), ROUND(AVG(load_15min), 2),
                    ROUND(AVG(running_tasks), 2), ROUND(AVG(total_tasks), 2),
                    ROUND(SUM(cpu_user), 2), ROUND(SUM(cpu_system), 2), ROUND(SUM(cpu_nice), 2),
                    ROUND(SUM(cpu_idle), 2), ROUND(SUM(cpu_iowait), 2), ROUND(SUM(cpu_irq), 2), ROUND(SUM(cpu_softirq), 2), ROUND(SUM(cpu_steal), 2),
                    ROUND(AVG(mem_total_mib), 2), ROUND(AVG(mem_free_mib), 2), ROUND(AVG(mem_used_mib), 2), ROUND(AVG(mem_buff_cache_mib), 2),
                    ROUND(AVG(tcp_connections), 2), ROUND(AVG(udp_connections), 2),
                    SUM(default_interface_net_rx_bytes), SUM(default_interface_net_tx_bytes),
                    ROUND(AVG(cpu_num_cores), 2), ROUND(AVG(cpu_delay_us), 2), ROUND(AVG(disk_delay_us), 2),
                    ROUND(AVG(root_disk_total_kb), 2), ROUND(AVG(root_disk_avail_kb), 2),
                    SUM(reads_completed), SUM(writes_completed),
                    SUM(reading_ms), SUM(writing_ms), SUM(iotime_ms),
                    ROUND(AVG(ios_in_progress), 2), ROUND(SUM(weighted_io_time), 2)
                FROM status_minutes
                WHERE 
                    client_id = ? 
                    AND timestamp >= ? - 3600
                GROUP BY client_id;
                """,
                (client_id, kunlun_report_line.timestamp),
            )

            # 清理超出上限的小时级数据
            cursor.execute(
                """
                DELETE FROM status_hours
                WHERE (client_id, timestamp) IN (
                    SELECT client_id, timestamp FROM status_hours
                    WHERE client_id = ? ORDER BY timestamp DESC LIMIT -1  OFFSET 8760
                );
            """,  # 保留最新 8760 条（365天）
                (client_id,),
            )
            conn.commit()

    return JSONResponse(status_code=200, content={"ok": 2})


@app.get("/status")
async def route_get_status():
    return Response(content="kunlun", media_type="text/plain")


@app.get("/status/latest")
async def get_status_latest():
    """
    获取所有客户端的最新状态数据，并包含 machine_id 和 hostname。
    - 每个客户端只返回最新的一条记录。
    """
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.row_factory = sqlite3.Row
        # 使用 JOIN 查询 status_latest 和 client 表，并只返回每个客户端的最新一条记录
        cursor.execute(
            """
            SELECT sl.*, c.machine_id, c.hostname
            FROM status_latest sl
            JOIN client c ON sl.client_id = c.id
            WHERE sl.timestamp = (
                SELECT MAX(timestamp)
                FROM status_latest
                WHERE client_id = sl.client_id
            )
            """
        )
        results = cursor.fetchall()
        return JSONResponse(content=[dict(row) for row in results])


@app.get("/status/seconds")
async def get_status_seconds(client_id: int, limit: int = 360):
    """
    获取整理计算后的 10 秒级数据。
    - client_id: 客户端 ID
    - limit: 返回的记录数，默认为 360（1 小时数据）
    """
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(
            "SELECT * FROM status_seconds WHERE client_id = ? ORDER BY timestamp DESC LIMIT ?",
            (client_id, limit),
        )
        return JSONResponse(content=[dict(row) for row in cursor.fetchall()])


@app.get("/status/minutes")
async def get_status_minutes(client_id: int, limit: int = 1440):
    """
    获取整理计算后的分钟级数据。
    - client_id: 客户端 ID
    - limit: 返回的记录数，默认为 1440（24 小时数据）
    """
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(
            "SELECT * FROM status_minutes WHERE client_id = ? ORDER BY timestamp DESC LIMIT ?",
            (client_id, limit),
        )
        return JSONResponse(content=[dict(row) for row in cursor.fetchall()])


@app.get("/status/hours")
async def get_status_hours(client_id: int, limit: int = 8760):
    """
    获取整理计算后的小时级数据。
    - client_id: 客户端 ID
    - limit: 返回的记录数，默认为 8760（365 天数据）
    """
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(
            "SELECT * FROM status_hours WHERE client_id = ? ORDER BY timestamp DESC LIMIT ?",
            (client_id, limit),
        )
        return JSONResponse(content=[dict(row) for row in cursor.fetchall()])



@app.get("/")
async def route_get_index():
    with open("./kunlun.html", "rt", encoding="utf-8") as html:
        return Response(content=html.read(), media_type="text/html")


@app.get("/{p:path}")
async def not_found_handler(p: str):
    """
    兜底页面
    """
    return Response(
        status_code=404,
        content='''
        <center style='
            display: flex;
            align-items: center;
            justify-content: center;
            width: 100%;
            height: 100%;
            position: fixed;'>
            准备中...
        </center>
        ''',
        media_type="text/html",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="::", port=8008)
