# -*- coding: utf-8 -*-
"""配置：本地 Mosquitto / 真实 OneNET 一键切换"""

MODE = "LOCAL"                     # LOCAL=本地Mosquitto / REAL=真实OneNET

PRODUCT_ID = "admin"          # 模拟产品ID
GW_DEVICE_NAME = "gw0001"          # 网关设备名（clientId）
GW_DEVICE_KEY = "7Qk1T6lGzP0aB9C8d7E6f5A4b3C2D1E0F9a8B7C6D5E="  # 真实环境用

LOCAL_BROKER = {"host": "127.0.0.1", "port": 1883}
LOCAL_PASSWORD = "123456"          # 与 mosquitto_passwd 设置一致
REAL_BROKER = {"host": "mqtts.heclouds.com", "port": 1883}

# 10台断路器（deviceName=SN）
BREAKER_SNS = [f"8900000012{34 + i}" for i in range(10)]

DB_PATH = "gateway.db"

# pack/post 主题（新版物模型批量上报）
def topic_pack_post():
    return f"$sys/{PRODUCT_ID}/{GW_DEVICE_NAME}/thing/pack/post"

def topic_pack_reply():
    return f"$sys/{PRODUCT_ID}/{GW_DEVICE_NAME}/thing/pack/post/reply"
