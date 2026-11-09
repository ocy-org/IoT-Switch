# -*- coding: utf-8 -*-
"""SQLite 建表/写入/读取/标记
"""
import sqlite3
import pg_config as cfg

DDL = """
CREATE TABLE IF NOT EXISTS breaker_device(          --设备档案
    sn TEXT PRIMARY KEY, dev_class TEXT, dev_type INTEGER,
    hw_ver TEXT, sw_ver TEXT, factory_date TEXT);
CREATE TABLE IF NOT EXISTS breaker_realtime(        --业务数据
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sn TEXT, status INTEGER,          -- 1开闸/2合闸/3离线
    voltage INTEGER,                  -- V
    current REAL,                     -- A (int+float*0.01已拼好)
    active_power REAL, reactive_power REAL,   -- W
    power_factor REAL,                -- 0~1 (已归一化)
    leakage INTEGER,                  -- mA
    kwh REAL,                         -- KWH
    switch_count INTEGER, half_hour_slot INTEGER,   -- 次数/1-48槽位
    report_time TEXT,
    synced INTEGER DEFAULT 0);        -- 0=未推送 1=已推送
CREATE TABLE IF NOT EXISTS breaker_alarm(           -- 错误码事件
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sn TEXT, alarm_code INTEGER,      -- 32位bitMap原值
    re_close INTEGER,                 -- 重合闸次数
    level INTEGER,                    -- 1预警/2报警
    report_time TEXT,
    synced INTEGER DEFAULT 0);
"""


def _conn():
    c = sqlite3.connect(cfg.DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with _conn() as c:
        c.executescript(DDL)


def insert_realtime(rows: list):
    with _conn() as c:
        c.executemany("""INSERT INTO breaker_realtime
            (sn,status,voltage,current,active_power,reactive_power,
             power_factor,leakage,kwh,switch_count,half_hour_slot,
             report_time) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", rows)


def insert_alarm(rows: list):
    with _conn() as c:
        c.executemany("""INSERT INTO breaker_alarm
            (sn,alarm_code,re_close,level,report_time)
            VALUES(?,?,?,?,?)""", rows)


def insert_devices(rows: list):
    with _conn() as c:
        c.executemany("""INSERT OR IGNORE INTO breaker_device
            (sn,dev_class,dev_type,hw_ver,sw_ver,factory_date)
            VALUES(?,?,?,?,?,?)""", rows)


#获取为上报的业务信息，推送到ONENET物理平台
def fetch_unsynced_realtime() -> list:
    """每台SN取最新一条未同步的实时数据"""
    with _conn() as c:
        return [dict(r) for r in c.execute("""
            SELECT * FROM breaker_realtime WHERE synced=0
            AND id IN (SELECT MAX(id) FROM breaker_realtime
                       WHERE synced=0 GROUP BY sn)""")]

#获取为上报的事件信息，推送到ONENET物理平台
def fetch_unsynced_alarms() -> list:
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM breaker_alarm WHERE synced=0")]

#更新推送标识
def mark_synced(realtime_ids: list, alarm_ids: list):
    with _conn() as c:
        if realtime_ids:
            c.executemany("UPDATE breaker_realtime SET synced=1 WHERE id=?",
                          [(i,) for i in realtime_ids])
        if alarm_ids:
            c.executemany("UPDATE breaker_alarm SET synced=1 WHERE id=?",
                          [(i,) for i in alarm_ids])


def stat():
    with _conn() as c:
        return {
            "devices": c.execute(
                "SELECT COUNT(*) FROM breaker_device").fetchone()[0],
            "rt_unsynced": c.execute(
                "SELECT COUNT(*) FROM breaker_realtime WHERE synced=0"
            ).fetchone()[0],
            "rt_total": c.execute(
                "SELECT COUNT(*) FROM breaker_realtime").fetchone()[0],
            "alarm_unsynced": c.execute(
                "SELECT COUNT(*) FROM breaker_alarm WHERE synced=0"
            ).fetchone()[0],
        }
