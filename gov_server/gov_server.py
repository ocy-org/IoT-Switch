# -*- coding: utf-8 -*-
"""政务网接收服务（独立运行版，无外部依赖文件）
  HTTP POST /onenet/push -> 解析 -> 写入 gateway.db (gov_*表)
运行: python gov_server.py
"""
import sqlite3
import sys
import time

from flask import Flask, jsonify, request

# ==================== 配置区（按环境修改这里） ====================
HTTP_PORT    = 8000                          # 监听端口
DB_PATH      = "gateway.db"                  # 政务网侧数据库名（与网关侧同名）
# 政务网侧表名: gov_realtime_data / gov_alarm_event（与网关侧表名不同）
# =================================================================

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

app = Flask(__name__)

DDL = """
CREATE TABLE IF NOT EXISTS gov_realtime_data(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sn TEXT, status INTEGER,
    voltage INTEGER, current REAL,
    active_power REAL, reactive_power REAL,
    power_factor REAL, leakage INTEGER, kwh REAL,
    switch_count INTEGER, half_hour_slot INTEGER,
    push_time TEXT, recv_time TEXT);
CREATE TABLE IF NOT EXISTS gov_alarm_event(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sn TEXT, alarm_code INTEGER,
    re_close INTEGER, level INTEGER,
    push_time TEXT, recv_time TEXT);
"""


def db_conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with db_conn() as c:
        c.executescript(DDL)


@app.route("/onenet/push", methods=["POST"])
def onenet_push():
    body = request.get_json(silent=True)
    if not body or "device_name" not in body:
        return jsonify(code=400, msg="bad json"), 400

    sn = body["device_name"]
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    props = body.get("properties", {})
    events = body.get("events", {})

    try:
        with db_conn() as c:
            if props:
                c.execute("""INSERT INTO gov_realtime_data
                    (sn,status,voltage,current,active_power,reactive_power,
                     power_factor,leakage,kwh,switch_count,half_hour_slot,
                     push_time,recv_time)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                    sn, props.get("status"), props.get("voltage"),
                    props.get("current"), props.get("active_power"),
                    props.get("reactive_power"), props.get("power_factor"),
                    props.get("leakage"), props.get("kwh"),
                    props.get("switch_count"), props.get("half_hour_slot"),
                    ts, ts))
            if "error_report" in events:
                v = events["error_report"]
                c.execute("""INSERT INTO gov_alarm_event
                    (sn,alarm_code,re_close,level,push_time,recv_time)
                    VALUES(?,?,?,?,?,?)""", (
                    sn, v.get("alarm_code"), v.get("re_close"),
                    v.get("level"), ts, ts))
    except sqlite3.Error as e:
        return jsonify(code=500, msg=f"db error: {e}"), 500

    print(f"[RECV] sn={sn} props={len(props)} events={len(events)} -> 入库")
    return jsonify(code=200, msg="ok")


@app.route("/query", methods=["GET"])
def query():
    with db_conn() as c:
        rt = [dict(r) for r in c.execute(
            "SELECT * FROM gov_realtime_data ORDER BY id DESC LIMIT 10")]
        al = [dict(r) for r in c.execute(
            "SELECT * FROM gov_alarm_event ORDER BY id DESC LIMIT 10")]
    return jsonify(realtime=rt, alarms=al)


if __name__ == "__main__":
    init_db()
    print(f"[GOV] 接收服务已启动: 0.0.0.0:{HTTP_PORT}  数据库: {DB_PATH}")
    app.run(host="0.0.0.0", port=HTTP_PORT)
