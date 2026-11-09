# -*- coding: utf-8 -*-
"""从 SQLite 读未同步数据 -> 组 pack/post -> 推 MQTT broker -> 成功后标记
运行: python push_data.py
"""
import json
import sys
import time

import paho.mqtt.client as mqtt

import pg_config as cfg
import db

# Windows 控制台中文防乱码
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")


def build_payload(rt_rows: list, alarm_rows: list) -> str:
    """pack/post 载荷：params数组，每元素一台设备（properties+events）"""
    alarm_by_sn = {a["sn"]: a for a in alarm_rows}
    ts = int(time.time() * 1000)
    params = []
    for r in rt_rows:
        item = {
            "identity": {"productID": "", "deviceName": r["sn"]},
            "properties": {
                "status":         {"value": r["status"], "time": ts},
                "voltage":        {"value": r["voltage"], "time": ts},
                "current":        {"value": r["current"], "time": ts},
                "active_power":   {"value": r["active_power"], "time": ts},
                "reactive_power": {"value": r["reactive_power"], "time": ts},
                "power_factor":   {"value": r["power_factor"], "time": ts},
                "leakage":        {"value": r["leakage"], "time": ts},
                "kwh":            {"value": r["kwh"], "time": ts},
                "switch_count":   {"value": r["switch_count"], "time": ts},
                "half_hour_slot": {"value": r["half_hour_slot"], "time": ts},
            },
        }
        a = alarm_by_sn.get(r["sn"])
        if a:
            item["events"] = {"error_report": {
                "value": {"alarm_code": a["alarm_code"],
                          "re_close": a["re_close"],
                          "level": a["level"]}, "time": ts}}
        params.append(item)
    payload = {"id": str(int(time.time()))[-10:], "version": "1.0",
               "params": params}
    return json.dumps(payload, ensure_ascii=False)


def main():
    rows_rt = db.fetch_unsynced_realtime()
    rows_alarm = db.fetch_unsynced_alarms()
    if not rows_rt:
        print("没有未推送数据。先运行 python gen_data.py 造数据")
        return
    print(f"[DB] 待推送: 实时{len(rows_rt)}台 告警{len(rows_alarm)}条")

    payload = build_payload(rows_rt, rows_alarm)
    print(f"[PACK] {len(payload)} bytes, devices={len(rows_rt)}")

    # 连接（LOCAL=固定密码 / REAL=token）
    if cfg.MODE == "LOCAL":
        host = cfg.LOCAL_BROKER["host"]; port = cfg.LOCAL_BROKER["port"]
        password = cfg.LOCAL_PASSWORD
    else:
        from onenet_token import gen_token
        host = cfg.REAL_BROKER["host"]; port = cfg.REAL_BROKER["port"]
        password = gen_token(cfg.PRODUCT_ID, cfg.GW_DEVICE_NAME,
                             cfg.GW_DEVICE_KEY)

    client = mqtt.Client(client_id=cfg.GW_DEVICE_NAME)
    client.username_pw_set(cfg.PRODUCT_ID, password)
    client.connect(host, port, keepalive=60)       # 阻塞式连接，失败直接报错
    client.loop_start()                            # 启动网络线程

    topic = cfg.topic_pack_post()
    info = client.publish(topic, payload, qos=0)   # QoS0：发出即不管
    info.wait_for_publish()                        # 关键：等消息真正写出网络再断开

    db.mark_synced([r["id"] for r in rows_rt],
                   [a["id"] for a in rows_alarm])
    print(f"[PUB] {topic}")
    print("[STAT]", db.stat())

    client.loop_stop()
    client.disconnect()


if __name__ == "__main__":
    main()