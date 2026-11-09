# -*- coding: utf-8 -*-
"""发送程序：读SQLite待发送告警 -> 按龙华智慧用电接口组装bean -> POST大数据平台
接口文档: 龙华党建社区治理接口-智慧用电(20190902) 接口1 事件入库 ai_eventSend/query
关键点: Map.put("bean", json字符串) -> 外层JSON的bean字段是"字符串包裹的JSON"
运行: python bigdata_sender.py             # 处理一轮待发送
      python bigdata_sender.py --loop 60   # 常驻循环，每60秒一轮
"""
import argparse
import json
import sys
import time

import requests

import gov_common as gc

# ==================== 配置区 ====================
# 测试地址(AITEST) / 正式地址(AI)，上线时切换
#BIGDATA_URL = "http://xxx.xxx.xxx.xxx:8001/AITEST/restservices/api/ai_eventSend/query"
# 本地闭环测试改为: "http://127.0.0.1:5000/mock/bigdata"
BIGDATA_URL = "http://127.0.0.1:5000/mock/bigdata"
TIMEOUT = 10

EVENTTYPE    = "060704"    # 安全隐患-线路消防安全-危险用电（文档eventtype代码表）
EVENTCONTENT = "危险用电"
EVENTSOURCE  = "12"        # 事件来源: 智慧用电（EventEventSource代码表）
FIXED_PERSON = "智慧用电"   # 文档备注固定传值
TRANO_PREFIX = "ZHNY"      # 转来文号前缀（第三方自定义唯一号）
# ================================================

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")


def fetch_unsent():
    """待发送 = 推送日志中没有 return_code='1' 成功记录的告警"""
    with gc.db_conn() as c:
        return [dict(r) for r in c.execute("""
            SELECT a.* FROM gov_alarm_event a
            WHERE NOT EXISTS (SELECT 1 FROM gov_push_log p
                              WHERE p.alarm_id=a.id AND p.return_code='1')
            ORDER BY a.id""")]


def fetch_location(sn):
    with gc.db_conn() as c:
        row = c.execute("SELECT * FROM gov_device_location WHERE sn=?", (sn,)).fetchone()
    return dict(row) if row else None


def build_bean(alarm: dict, loc: dict) -> dict:
    """接口1事件字段组装（必填项全齐，字段来源见对照表）"""
    sn = alarm["sn"]
    bits = gc.bits_to_text(alarm["alarm_code"])
    return {
        # id 不传 -> 平台自动赋值（文档原文，用于查询事件流程）
        "areaid":         loc["areaid"],            # 必填 18位区域码
        "registerperson": loc["registerperson"],    # 必填
        "registerphone":  loc["registerphone"],     # 必填
        "disposalperson": FIXED_PERSON,             # 受理人: 智慧用电
        "sitetype":       loc["sitetype"],          # 必填 1室内/2户外
        "place":          loc["place"],             # 必填 场所地址
        "gisp_x":         loc["gisp_x"],            # 必填 坐标X
        "gisp_y":         loc["gisp_y"],            # 必填 坐标Y
        "eventtype":      EVENTTYPE,                # 必填 危险用电
        "eventcontent":   EVENTCONTENT,
        "eventsource":    EVENTSOURCE,              # 必填 12智慧用电
        "problem":        f"设备[{sn}]用电异常: {bits} (错误码0x{alarm['alarm_code']:X})",
        "isturn":         "1",                      # 必填 是否转来件
        "trano":          f"{TRANO_PREFIX}{alarm['id']:010d}",  # 自定义唯一号
        "tranotime":      alarm["recv_time"],     # 格式已符合 yyyy-MM-dd HH:mm:ss
        "pda_user":       FIXED_PERSON,             # 必填 采集员
        "netperson":      FIXED_PERSON,             # 必填 网格员
        "canselfsubmit":  "0",                      # 必填 自行提交
    }


def retry_count(alarm_id):
    with gc.db_conn() as c:
        return c.execute("SELECT COUNT(*) FROM gov_push_log WHERE alarm_id=?",
                         (alarm_id,)).fetchone()[0]


def log_push(alarm, trano, req_body, resp, ok):
    with gc.db_conn() as c:
        c.execute("""INSERT INTO gov_push_log
            (alarm_id,sn,trano,request_body,response_body,return_code,send_time,retry_count)
            VALUES(?,?,?,?,?,?,?,?)""",
            (alarm["id"], alarm["sn"], trano, req_body,
             json.dumps(resp, ensure_ascii=False),
             "1" if ok else "0", gc.now(), retry_count(alarm["id"]) + 1))


def send_one(alarm: dict) -> bool:
    loc = fetch_location(alarm["sn"])
    if not loc or not loc["place"]:
        print(f"[SKIP] 告警#{alarm['id']} 设备{alarm['sn']} 未配置位置信息, "
              f"请先在Web'设备位置'菜单填写(下轮自动重试)")
        return False

    bean = build_bean(alarm, loc)
    trano = bean["trano"]
    # 关键: bean是"字符串包裹的JSON"（等价于文档 Map.put("bean", json字符串)）
    payload = json.dumps({"bean": json.dumps(bean, ensure_ascii=False)},
                         ensure_ascii=False)
    try:
        r = requests.post(BIGDATA_URL, data=payload.encode("utf-8"),
                          headers={"Content-Type": "application/json;charset=utf-8"},
                          timeout=TIMEOUT)
        try:
            resp = r.json()
        except ValueError:
            resp = {"return_code": "0", "return_tips": r.text[:120]}
    except Exception as e:
        resp = {"return_code": "0", "return_tips": f"网络异常: {e}"}

    ok = str(resp.get("return_code")) == "1"    # 注意: 文档return_code是字符串"1"
    log_push(alarm, trano, payload, resp, ok)
    tag = "OK  " if ok else "FAIL"
    print(f"[{tag}] 告警#{alarm['id']} trano={trano} -> "
          f"{resp.get('return_tips','')} {resp.get('return_info','')}")
    return ok


def run_batch():
    gc.init_db()
    rows = fetch_unsent()
    print(f"[SEND] 待发送告警 {len(rows)} 条 -> {BIGDATA_URL}")
    ok = sum(1 for a in rows if send_one(a))
    print(f"[DONE] 成功 {ok}/{len(rows)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", type=int, default=0,
                    help="循环间隔秒数, 0=执行一次退出")
    args = ap.parse_args()
    if args.loop > 0:
        while True:
            run_batch()
            time.sleep(args.loop)
    else:
        run_batch()


if __name__ == "__main__":
    main()
