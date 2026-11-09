# -*- coding: utf-8 -*-
"""生成一轮测试数据写入 SQLite：10台断路器档案 + 实时数据 + 1台告警
字段语义与《二代网关mqtt通讯.doc》35H/36H/33H 一一对应
运行: python gen_data.py   （可反复运行，每次追加一轮数据）
"""
import random
import time

import pg_config as cfg
import db

ALARM_SN = cfg.BREAKER_SNS[2]          # 第3台造一条告警


def main():
    db.init_db()

    # ---- 33H 设备档案（重复运行不重复插）----
    devices = [(sn, random.choice(["32A", "63A", "100A"]), 2,
                "HW2.1.0", "SW3.0.5",
                time.strftime("%Y%m%d", time.strptime("2024-06-01", "%Y-%m-%d")))
               for sn in cfg.BREAKER_SNS]
    db.insert_devices(devices)

    # ---- 35H 实时数据（一轮10台）----
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    slot = (int(time.strftime("%H")) * 60 + int(time.strftime("%M"))) // 30 + 1
    rt_rows = []
    for sn in cfg.BREAKER_SNS:
        rt_rows.append((
            sn,
            random.choice([1, 2, 2, 2]),                      # status
            random.randint(215, 230),                          # voltage V
            round(random.uniform(2, 18), 2),                   # current A
            round(random.uniform(400, 4000), 1),               # active_power W
            round(random.uniform(50, 500), 1),                 # reactive_power W
            round(random.uniform(0.82, 0.98), 2),              # power_factor
            random.randint(0, 3),                              # leakage mA
            round(random.uniform(1000, 2000), 2),              # kwh
            random.randint(100, 900),                          # switch_count
            slot,                                              # half_hour_slot
            now,
        ))
    db.insert_realtime(rt_rows)

    # ---- 36H 告警（ALARM_SN: 0x44=bit2过流+bit6温度过高）----
    alarm_rows = [(ALARM_SN, 0x44, 0, 2, now)]
    db.insert_alarm(alarm_rows)

    print("本轮数据已写入:", db.stat())


if __name__ == "__main__":
    main()
