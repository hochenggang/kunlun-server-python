import os
import logging
import sqlite3
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field
from fastapi import FastAPI, Form, Response, Request, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

os.makedirs("db", exist_ok=True)
DATABASE = "db/kunlun_status.db"


class FieldType(str, Enum):
    COUNTER = "counter"
    GAUGE = "gauge"


class KunlunReportLine(BaseModel):
    client_id: Optional[int] = Field(default=None, json_schema_extra={"field_type": FieldType.GAUGE})
    timestamp: int = Field(json_schema_extra={"field_type": FieldType.GAUGE})
    uptime_s: int = Field(json_schema_extra={"field_type": FieldType.GAUGE})
    load_1min: float = Field(json_schema_extra={"field_type": FieldType.GAUGE})
    load_5min: float = Field(json_schema_extra={"field_type": FieldType.GAUGE})
    load_15min: float = Field(json_schema_extra={"field_type": FieldType.GAUGE})
    running_tasks: int = Field(json_schema_extra={"field_type": FieldType.GAUGE})
    total_tasks: int = Field(json_schema_extra={"field_type": FieldType.GAUGE})
    cpu_user: float = Field(json_schema_extra={"field_type": FieldType.COUNTER})
    cpu_system: float = Field(json_schema_extra={"field_type": FieldType.COUNTER})
    cpu_nice: float = Field(json_schema_extra={"field_type": FieldType.COUNTER})
    cpu_idle: float = Field(json_schema_extra={"field_type": FieldType.COUNTER})
    cpu_iowait: float = Field(json_schema_extra={"field_type": FieldType.COUNTER})
    cpu_irq: float = Field(json_schema_extra={"field_type": FieldType.COUNTER})
    cpu_softirq: float = Field(json_schema_extra={"field_type": FieldType.COUNTER})
    cpu_steal: float = Field(json_schema_extra={"field_type": FieldType.COUNTER})
    mem_total_mib: float = Field(json_schema_extra={"field_type": FieldType.GAUGE})
    mem_free_mib: float = Field(json_schema_extra={"field_type": FieldType.GAUGE})
    mem_used_mib: float = Field(json_schema_extra={"field_type": FieldType.GAUGE})
    mem_buff_cache_mib: float = Field(json_schema_extra={"field_type": FieldType.GAUGE})
    tcp_connections: int = Field(json_schema_extra={"field_type": FieldType.GAUGE})
    udp_connections: int = Field(json_schema_extra={"field_type": FieldType.GAUGE})
    default_interface_net_rx_bytes: int = Field(json_schema_extra={"field_type": FieldType.COUNTER})
    default_interface_net_tx_bytes: int = Field(json_schema_extra={"field_type": FieldType.COUNTER})
    cpu_num_cores: int = Field(json_schema_extra={"field_type": FieldType.GAUGE})
    root_disk_total_kb: int = Field(json_schema_extra={"field_type": FieldType.GAUGE})
    root_disk_avail_kb: int = Field(json_schema_extra={"field_type": FieldType.GAUGE})
    reads_completed: int = Field(json_schema_extra={"field_type": FieldType.COUNTER})
    writes_completed: int = Field(json_schema_extra={"field_type": FieldType.COUNTER})
    reading_ms: int = Field(json_schema_extra={"field_type": FieldType.COUNTER})
    writing_ms: int = Field(json_schema_extra={"field_type": FieldType.COUNTER})
    iotime_ms: int = Field(json_schema_extra={"field_type": FieldType.COUNTER})
    ios_in_progress: int = Field(json_schema_extra={"field_type": FieldType.GAUGE})
    weighted_io_time: int = Field(json_schema_extra={"field_type": FieldType.COUNTER})
    machine_id: Optional[str] = Field(default=None, json_schema_extra={"field_type": FieldType.GAUGE})
    hostname: Optional[str] = Field(default="unknown", json_schema_extra={"field_type": FieldType.GAUGE})


EXCLUDED_FIELDS = {"client_id", "machine_id", "hostname"}


def get_status_fields() -> list[str]:
    return [f for f in KunlunReportLine.model_fields.keys() if f not in EXCLUDED_FIELDS]


def get_counter_fields() -> list[str]:
    return [
        f for f, field in KunlunReportLine.model_fields.items()
        if field.json_schema_extra.get("field_type") == FieldType.COUNTER
    ]


def get_gauge_fields() -> list[str]:
    return [
        f for f, field in KunlunReportLine.model_fields.items()
        if field.json_schema_extra.get("field_type") == FieldType.GAUGE and f not in EXCLUDED_FIELDS
    ]


def get_db_column_def() -> str:
    type_map = {
        int: "INTEGER NOT NULL",
        float: "REAL NOT NULL",
    }
    columns = []
    for name in get_status_fields():
        field = KunlunReportLine.model_fields[name]
        db_type = type_map.get(field.annotation, "TEXT")
        columns.append(f"{name} {db_type}")
    return ",\n            ".join(columns)


def rows_to_table(rows: list[dict]) -> list[list]:
    if not rows:
        return []
    headers = list(rows[0].keys())
    return [headers] + [list(row.values()) for row in rows]


def generate_insert_query(table_name: str, fields: list) -> str:
    fields_str = ", ".join(fields)
    placeholders = ", ".join(["?"] * len(fields))
    return f"INSERT OR REPLACE INTO {table_name} ({fields_str}) VALUES ({placeholders})"


def generate_aggregate_sql(source_table: str, target_table: str, interval_seconds: int) -> str:
    status_fields = get_status_fields()
    counter_fields = get_counter_fields()
    
    select_parts = ["client_id", "MAX(timestamp) AS timestamp"]
    for f in status_fields:
        if f in ("client_id", "timestamp"):
            continue
        if f in counter_fields:
            select_parts.append(f"SUM({f}) AS {f}")
        else:
            select_parts.append(f"ROUND(AVG({f}), 2) AS {f}")
    
    insert_fields = ["client_id", "timestamp"] + [f for f in status_fields if f not in ("client_id", "timestamp")]
    
    return f"""
        INSERT INTO {target_table} ({', '.join(insert_fields)})
        SELECT {', '.join(select_parts)}
        FROM {source_table}
        WHERE client_id = ? AND timestamp >= ? - {interval_seconds}
        GROUP BY client_id
    """


STATUS_FIELDS = get_status_fields()
COUNTER_FIELDS = get_counter_fields()
GAUGE_FIELDS = get_gauge_fields()
FIELDS_LIST = STATUS_FIELDS + ["machine_id", "hostname"]


def init_db():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=10000;")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS client (
                id INTEGER PRIMARY KEY NOT NULL,
                ip TEXT,
                machine_id TEXT UNIQUE NOT NULL,
                hostname TEXT NOT NULL,
                status INTEGER NOT NULL DEFAULT 0,
                last_update INTEGER NOT NULL,
                create_ts INTEGER NOT NULL
            )
        """)

        columns = get_db_column_def()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS status_latest (
                client_id INTEGER PRIMARY KEY,
                {columns},
                FOREIGN KEY (client_id) REFERENCES client(id)
            )
        """)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS status_seconds (
                client_id INTEGER NOT NULL,
                {columns},
                PRIMARY KEY (client_id, timestamp),
                FOREIGN KEY (client_id) REFERENCES client(id)
            )
        """)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS status_minutes (
                client_id INTEGER NOT NULL,
                {columns},
                PRIMARY KEY (client_id, timestamp),
                FOREIGN KEY (client_id) REFERENCES client(id)
            )
        """)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS status_hours (
                client_id INTEGER NOT NULL,
                {columns},
                PRIMARY KEY (client_id, timestamp),
                FOREIGN KEY (client_id) REFERENCES client(id)
            )
        """)
        conn.commit()

        cursor.execute("PRAGMA table_info(client)")
        cols = [col[1] for col in cursor.fetchall()]
        if 'status' not in cols:
            cursor.execute("ALTER TABLE client ADD COLUMN status INTEGER NOT NULL DEFAULT 0")
        if 'last_update' not in cols:
            cursor.execute("ALTER TABLE client ADD COLUMN last_update INTEGER NOT NULL DEFAULT 0")
        if 'ip' not in cols:
            cursor.execute("ALTER TABLE client ADD COLUMN ip TEXT")
        conn.commit()


init_db()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import time


def db_get_client_id(machine_id: str, hostname: str, client_ip: str) -> tuple[int, int]:
    current_ts = int(time.time())
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.row_factory = sqlite3.Row

        cursor.execute(
            "SELECT id, hostname, status FROM client WHERE machine_id = ?", (machine_id,)
        )
        client = cursor.fetchone()

        if client is None:
            cursor.execute("SELECT MAX(id) AS max_id FROM client")
            max_id_result = cursor.fetchone()
            new_id = (
                1 if max_id_result["max_id"] is None else max_id_result["max_id"] + 1
            )

            cursor.execute(
                "INSERT INTO client (id, machine_id, hostname, status, ip, last_update, create_ts) VALUES (?, ?, ?, 0, ?, ?, ?)",
                (new_id, machine_id, hostname, client_ip, current_ts, current_ts),
            )
            client_id = new_id
            status = 0
            logger.info(
                f"New client inserted: machine_id={machine_id}, client_id={client_id}, status=0"
            )
        else:
            client_id = client["id"]
            status = client["status"]
            if client["hostname"] != hostname:
                cursor.execute(
                    "UPDATE client SET hostname = ?, ip = ?, last_update = ? WHERE id = ?",
                    (hostname, client_ip, current_ts, client_id),
                )
                logger.info(
                    f"Hostname updated: client_id={client_id}, new_hostname={hostname}"
                )
            else:
                cursor.execute(
                    "UPDATE client SET ip = ?, last_update = ? WHERE id = ?",
                    (client_ip, current_ts, client_id),
                )

        conn.commit()
        return client_id, status


def calculate_delta(new_data: KunlunReportLine, last_data: KunlunReportLine) -> KunlunReportLine:
    delta_data = {}
    for name, field in KunlunReportLine.model_fields.items():
        field_type = field.json_schema_extra.get("field_type", FieldType.GAUGE)
        new_val = getattr(new_data, name)
        old_val = getattr(last_data, name)
        
        if field_type == FieldType.COUNTER and old_val is not None and new_val is not None:
            delta_data[name] = new_val - old_val
        else:
            delta_data[name] = new_val
    
    return KunlunReportLine(**delta_data)


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
    request: Request,
    values: str = Form(...),
):
    values_list = values.split(",")

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

    client_ip = request.client.host if request.client else "unknown"
    client_id, client_status = db_get_client_id(
        kunlun_report_line.machine_id, kunlun_report_line.hostname, client_ip
    )
    kunlun_report_line.client_id = client_id

    if client_status != 1:
        return JSONResponse(
            status_code=403,
            content={"error": "client not approved, status=0, waiting for admin approval"},
        )

    kunlun_report_line_before = None
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute("SELECT * FROM status_latest WHERE client_id = ?", (client_id,))
        last_data = cursor.fetchone()
        if last_data:
            kunlun_report_line_before = KunlunReportLine(**last_data)

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

    kunlun_report_line_delta_10s = calculate_delta(
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

        cursor.execute(
            """
            DELETE FROM status_seconds
            WHERE (client_id, timestamp) IN (
                SELECT client_id, timestamp FROM status_seconds
                WHERE client_id = ? ORDER BY timestamp DESC LIMIT -1 OFFSET 360
            );
            """,
            (client_id,),
        )
        conn.commit()

    if kunlun_report_line.timestamp % 60 == 0:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                generate_aggregate_sql("status_seconds", "status_minutes", 60),
                (client_id, kunlun_report_line.timestamp),
            )

            cursor.execute(
                """
                DELETE FROM status_minutes
                WHERE (client_id, timestamp) IN (
                    SELECT client_id, timestamp FROM status_minutes
                    WHERE client_id = ? ORDER BY timestamp DESC LIMIT -1 OFFSET 1440
                );
            """,
                (client_id,),
            )
            conn.commit()

    if kunlun_report_line.timestamp % 3600 == 0:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                generate_aggregate_sql("status_minutes", "status_hours", 3600),
                (client_id, kunlun_report_line.timestamp),
            )

            cursor.execute(
                """
                DELETE FROM status_hours
                WHERE (client_id, timestamp) IN (
                    SELECT client_id, timestamp FROM status_hours
                    WHERE client_id = ? ORDER BY timestamp DESC LIMIT -1 OFFSET 8760
                );
            """,
                (client_id,),
            )
            conn.commit()

    return JSONResponse(status_code=200, content={"ok": 2})


@app.get("/status")
async def route_get_status():
    return Response(content="kunlun", media_type="text/plain")


@app.get("/status/latest")
async def get_status_latest():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.row_factory = sqlite3.Row
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
        return JSONResponse(content=rows_to_table([dict(row) for row in results]))


@app.get("/status/seconds")
async def get_status_seconds(client_id: int, limit: int = 360):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(
            "SELECT * FROM status_seconds WHERE client_id = ? ORDER BY timestamp DESC LIMIT ?",
            (client_id, limit),
        )
        return JSONResponse(content=rows_to_table([dict(row) for row in cursor.fetchall()]))


@app.get("/status/minutes")
async def get_status_minutes(client_id: int, limit: int = 1440):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(
            "SELECT * FROM status_minutes WHERE client_id = ? ORDER BY timestamp DESC LIMIT ?",
            (client_id, limit),
        )
        return JSONResponse(content=rows_to_table([dict(row) for row in cursor.fetchall()]))


@app.get("/status/hours")
async def get_status_hours(client_id: int, limit: int = 8760):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(
            "SELECT * FROM status_hours WHERE client_id = ? ORDER BY timestamp DESC LIMIT ?",
            (client_id, limit),
        )
        return JSONResponse(content=rows_to_table([dict(row) for row in cursor.fetchall()]))


ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "Admin123")


def verify_admin_token(authorization: str = None) -> bool:
    if not authorization:
        return False
    authorization = authorization.strip()
    if authorization.startswith("Bearer "):
        token = authorization[7:]
    else:
        token = authorization
    return token == ADMIN_TOKEN


class AdminClientUpdate(BaseModel):
    machine_id: Optional[str] = None
    hostname: Optional[str] = None
    status: Optional[int] = None


@app.get("/admin/client")
async def admin_get_clients(authorization: str = Header(None)):
    if not verify_admin_token(authorization):
        return JSONResponse(status_code=401, content={"error": "unauthorized"})
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute("SELECT * FROM client ORDER BY id")
        results = cursor.fetchall()
        return JSONResponse(content=rows_to_table([dict(row) for row in results]))


@app.put("/admin/client/{client_id}")
async def admin_update_client(client_id: int, data: AdminClientUpdate, authorization: str = Header(None)):
    if not verify_admin_token(authorization):
        return JSONResponse(status_code=401, content={"error": "unauthorized"})
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute("SELECT * FROM client WHERE id = ?", (client_id,))
        client = cursor.fetchone()
        if not client:
            return JSONResponse(status_code=404, content={"error": "client not found"})
        updates = {}
        if data.machine_id is not None:
            updates["machine_id"] = data.machine_id
        if data.hostname is not None:
            updates["hostname"] = data.hostname
        if data.status is not None:
            updates["status"] = data.status
        if not updates:
            return JSONResponse(content={"ok": True, "message": "no fields to update"})
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [client_id]
        cursor.execute(f"UPDATE client SET {set_clause} WHERE id = ?", values)
        conn.commit()
        cursor.execute("SELECT * FROM client WHERE id = ?", (client_id,))
        updated_client = cursor.fetchone()
        return JSONResponse(content={"ok": True, "client": dict(updated_client)})


@app.delete("/admin/client/{client_id}")
async def admin_delete_client(client_id: int, authorization: str = Header(None)):
    if not verify_admin_token(authorization):
        return JSONResponse(status_code=401, content={"error": "unauthorized"})
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute("SELECT * FROM client WHERE id = ?", (client_id,))
        client = cursor.fetchone()
        if not client:
            return JSONResponse(status_code=404, content={"error": "client not found"})
        cursor.execute("DELETE FROM status_latest WHERE client_id = ?", (client_id,))
        cursor.execute("DELETE FROM status_seconds WHERE client_id = ?", (client_id,))
        cursor.execute("DELETE FROM status_minutes WHERE client_id = ?", (client_id,))
        cursor.execute("DELETE FROM status_hours WHERE client_id = ?", (client_id,))
        cursor.execute("DELETE FROM client WHERE id = ?", (client_id,))
        conn.commit()
        return JSONResponse(content={"ok": True, "message": f"client {client_id} and all related data deleted"})


KV = {}


@app.get("/")
async def route_get_index():
    key = 'index.html'
    if key not in KV:
        resp = requests.get("https://github.com/hochenggang/kunlun-frontend/releases/latest/download/index.html")
        KV[key] = resp.content
    
    return Response(content=KV[key], media_type="text/html")


@app.get("/{p:path}")
async def not_found_handler(p: str):
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
            404 Not Found
        </center>
        ''',
        media_type="text/html",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8008, log_level='error')
