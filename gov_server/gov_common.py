# -*- coding: utf-8 -*-
"""政务网侧共享模块：数据库连接/新表DDL/错误码翻译
gov_web.py 与 bigdata_sender.py 共用，保证同库同语义
"""
import sqlite3
import sys
import time

DB_PATH = "gateway.db"

# 32位错误码bitMap -> 异常项文字（对应网关36H错误码定义）
ALARM_BITS = {
    0: "漏电异常", 1: "短路异常", 2: "过流异常", 3: "过压异常",
    4: "欠压异常", 5: "缺相异常", 6: "温度过高异常", 7: "打火异常",
}

# 政务网侧新增两张表（与网关侧/接收侧表名均不同）
DDL = """
CREATE TABLE IF NOT EXISTS gov_device_location(   -- 接口必填字段维护(Web填写)
    sn TEXT PRIMARY KEY,
    areaid TEXT, place TEXT, gisp_x TEXT, gisp_y TEXT, sitetype TEXT,
    registerperson TEXT, registerphone TEXT,
    housecode TEXT, houseaddr TEXT,
    update_time TEXT);
CREATE TABLE IF NOT EXISTS gov_push_log(          -- 大数据平台推送日志
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alarm_id INTEGER, sn TEXT, trano TEXT,
    request_body TEXT, response_body TEXT,
    return_code TEXT, send_time TEXT, retry_count INTEGER DEFAULT 1);
"""


def db_conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with db_conn() as c:
        c.executescript(DDL)


def bits_to_text(code: int) -> str:
    names = [n for b, n in ALARM_BITS.items() if code & (1 << b)]
    return "、".join(names) if names else f"未知异常(0x{code:X})"


def now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
