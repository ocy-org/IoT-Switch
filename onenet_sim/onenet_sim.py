# -*- coding: utf-8 -*-
"""模拟OneNET平台数据流转（独立运行版，无外部依赖文件）
  订阅网关上行 pack/post -> 解析params -> 逐设备POST到政务网URL
运行: python onenet_sim.py
"""
import json
import sys
import time

import paho.mqtt.client as mqtt
import requests

# ==================== 配置区（按环境修改这里） ====================
BROKER_HOST   = "127.0.0.1"      # MQTT broker 地址
BROKER_PORT   = 1883
MQTT_USER     = "admin"             # broker 账号（与网关侧一致）
MQTT_PASS     = "123456"          # broker 密码（改成实际密码）

GW_NAME       = "gw0001"            # 网关设备名
TOPIC_PACK    = f"$sys/admin/{GW_NAME}/thing/pack/post"   # 完整主题(含pid=admin)

PUSH_URL      = "http://127.0.0.1:8000/onenet/push"       # 政务网接收地址
# =================================================================

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")


def build_push_body(item: dict) -> dict:
    """pack/post 中一台设备 -> 对政务网的POST体（模拟真实OneNET推送格式）"""
    props = {k: v["value"] for k, v in item.get("properties", {}).items()}
    events = {name: ev["value"] for name, ev in item.get("events", {}).items()}
    return {
        "product_id": "admin",
        "device_name": item["identity"]["deviceName"],
        "type": "pack",
        "properties": props,
        "events": events,
        "time": int(time.time() * 1000),
    }


def push_to_gov(body: dict):
    try:
        r = requests.post(PUSH_URL, json=body, timeout=5)
        print(f"[PUSH] {body['device_name']} http={r.status_code} "
              f"{'OK' if r.status_code == 200 else 'RETRY-NEEDED'}")
    except Exception as e:
        print(f"[FAIL] {body['device_name']} -> {e}")


def on_connect(client, userdata, flags, rc):
    print("[MQTT] connected rc =", rc)
    client.subscribe(TOPIC_PACK, qos=1)
    print("[MQTT] subscribed:", TOPIC_PACK)


def on_message(client, userdata, msg):
    print(f"\n[RECV] {msg.topic} ({len(msg.payload)} bytes)")
    try:
        body = json.loads(msg.payload)
    except ValueError:
        return print("[WARN] non-json payload")
    params = body.get("params", [])
    print(f"[PARSE] devices={len(params)}")
    for item in params:
        push_to_gov(build_push_body(item))


def main():
    client = mqtt.Client(client_id="onenet-sim")
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_connect, client.on_message = on_connect, on_message
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    print("[SIM] OneNET模拟器已启动, 推送目的地:", PUSH_URL)
    client.loop_forever()


if __name__ == "__main__":
    main()
