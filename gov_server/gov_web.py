# -*- coding: utf-8 -*-
"""智慧用电Web管理系统 (Flask, http://127.0.0.1:5000)
菜单: 驾驶舱 / 设备管理(档案+位置必填信息维护) / 设备实时数据 / 告警事件 / 推送日志
说明:
  - 设备管理 = 推送来的设备档案(SN/最近上报/累计告警) + 位置信息(接口必填)维护,
    位置的新增/编辑/删除入口都从这里进
  - 设备实时数据 = 纯业务数据(电压/电流/功率等), 不含位置等属性字段
  - UPSERT 兼容旧版SQLite(<3.24): 先UPDATE, rowcount==0 再INSERT
附带本地闭环测试用的模拟大数据平台: POST /mock/bigdata
运行: python gov_web.py
"""
from datetime import date, timedelta
from flask import (Flask, flash, jsonify, redirect, render_template,
                   request, url_for)

import gov_common as gc

app = Flask(__name__)
app.secret_key = "zhihui-yongdian-2024"

STATUS_TEXT = {1: "开闸", 2: "合闸", 3: "离线"}
# 接口1必填字段（位置表必须收集的）
REQ_FIELDS = ["areaid", "place", "gisp_x", "gisp_y",
              "sitetype", "registerperson", "registerphone"]

# 待推送 = 推送日志中无 return_code='1' 成功记录的告警
UNSENT_SQL = """SELECT COUNT(*) FROM gov_alarm_event a
 WHERE NOT EXISTS (SELECT 1 FROM gov_push_log p
                   WHERE p.alarm_id=a.id AND p.return_code='1')"""
# 告警列表: 附加 是否已推送 / 设备是否已配置位置 两个标记
ALARM_LIST_SQL = """SELECT a.*,
   EXISTS(SELECT 1 FROM gov_push_log p WHERE p.alarm_id=a.id AND p.return_code='1') AS sent,
   EXISTS(SELECT 1 FROM gov_device_location l WHERE l.sn=a.sn) AS hasloc
 FROM gov_alarm_event a WHERE 1=1"""


def decorate_alarm(r):
    d = dict(r)
    d["bits_text"] = gc.bits_to_text(d["alarm_code"])
    d["code_hex"] = f"0x{d['alarm_code']:02X}"
    d["level_text"] = {1: "预警", 2: "报警"}.get(d["level"], str(d["level"]))
    return d


# ================= 驾驶舱 =================
@app.route("/")
def index():
    with gc.db_conn() as c:
        stat = {
            "device_count": c.execute(
                "SELECT COUNT(DISTINCT sn) FROM gov_realtime_data").fetchone()[0],
            "alarm_today": c.execute(
                "SELECT COUNT(*) FROM gov_alarm_event "
                "WHERE substr(recv_time,1,10)=date('now','localtime')").fetchone()[0],
            "unsent": c.execute(UNSENT_SQL).fetchone()[0],
            "push_ok": c.execute(
                "SELECT COUNT(*) FROM gov_push_log WHERE return_code='1'").fetchone()[0],
        }
        stat["unsent_noloc"] = c.execute(UNSENT_SQL + """
            AND NOT EXISTS (SELECT 1 FROM gov_device_location l WHERE l.sn=a.sn)"""
        ).fetchone()[0]
        rows = c.execute(ALARM_LIST_SQL + " ORDER BY a.id DESC LIMIT 8").fetchall()
    return render_template("index.html", stat=stat,
                           alarms=[decorate_alarm(r) for r in rows],
                           active="index")


# ================= 设备管理（设备档案 + 位置信息维护） =================
@app.route("/devices")
def devices():
    with gc.db_conn() as c:
        rows = c.execute("""
            SELECT d.sn AS sn, d.last_seen AS last_seen, d.alarm_cnt AS alarm_cnt,
                   l.areaid AS areaid, l.place AS place, l.gisp_x AS gisp_x,
                   l.gisp_y AS gisp_y, l.sitetype AS sitetype,
                   l.registerperson AS registerperson,
                   l.registerphone AS registerphone
            FROM (SELECT u.sn AS sn,
                    (SELECT MAX(recv_time) FROM gov_realtime_data r
                      WHERE r.sn=u.sn) AS last_seen,
                    (SELECT COUNT(*) FROM gov_alarm_event a
                      WHERE a.sn=u.sn) AS alarm_cnt
                  FROM (SELECT DISTINCT sn FROM gov_realtime_data
                        UNION SELECT DISTINCT sn FROM gov_alarm_event) u) d
            LEFT JOIN gov_device_location l ON l.sn = d.sn
            ORDER BY d.sn""").fetchall()
    return render_template("devices.html", devs=[dict(r) for r in rows],
                           active="devices")


# ================= 设备实时数据（纯业务数据） =================
@app.route("/realtime")
def realtime():
    with gc.db_conn() as c:
        rows = c.execute("""SELECT r.* FROM gov_realtime_data r WHERE r.id IN
            (SELECT MAX(id) FROM gov_realtime_data GROUP BY sn) ORDER BY r.sn"""
        ).fetchall()
    devs = []
    for r in rows:
        d = dict(r)
        d["status_text"] = STATUS_TEXT.get(d["status"], str(d["status"]))
        devs.append(d)
    return render_template("realtime.html", devs=devs, active="realtime")


# ================= 告警事件 =================
@app.route("/alarms")
def alarms():
    today = date.today().strftime("%Y-%m-%d")
    # 无任何日期参数 -> 默认今天；带参数(可为空) -> 按参数筛选，都为空=全部
    if "date_from" not in request.args and "date_to" not in request.args:
        date_from = date_to = today
    else:
        date_from = request.args.get("date_from", "").strip()
        date_to = request.args.get("date_to", "").strip()

    cond, args = "", []
    if date_from:
        cond += " AND a.recv_time >= ?"         
        args.append(date_from + " 00:00:00")
    if date_to:
        cond += " AND a.recv_time <= ?"          
        args.append(date_to + " 23:59:59")

    with gc.db_conn() as c:
        rows = c.execute(ALARM_LIST_SQL + cond +
                         " ORDER BY a.id DESC LIMIT 500", args).fetchall()

    quick = {
        "today": today,
        "week":  (date.today() - timedelta(days=6)).strftime("%Y-%m-%d"),
        "month": (date.today() - timedelta(days=29)).strftime("%Y-%m-%d"),
    }
    return render_template("alarms.html",
                           alarms=[decorate_alarm(r) for r in rows],
                           date_from=date_from, date_to=date_to,
                           quick=quick, total=len(rows), active="alarms")


# ================= 位置信息维护（入口从设备管理进） =================
# 旧 /locations 列表页已合并进设备管理，跳转兼容
@app.route("/locations")
def locations():
    return redirect(url_for("devices"))


@app.route("/locations/edit", defaults={"sn": ""})
@app.route("/locations/edit/<sn>")
def location_edit(sn):
    with gc.db_conn() as c:
        row = c.execute("SELECT * FROM gov_device_location WHERE sn=?",
                        (sn,)).fetchone()
        all_sns = [r[0] for r in c.execute(
            "SELECT DISTINCT sn FROM gov_realtime_data "
            "UNION SELECT DISTINCT sn FROM gov_alarm_event")]
    loc = dict(row) if row else {"sn": sn}
    return render_template("location_form.html", loc=loc,
                           all_sns=all_sns, active="devices")


@app.route("/locations/save", methods=["POST"])
def location_save():
    f = {k: request.form.get(k, "").strip()
         for k in ["sn"] + REQ_FIELDS + ["housecode", "houseaddr"]}
    back = redirect(url_for("location_edit", sn=f["sn"]))

    # 必填项校验
    missing = [k for k in REQ_FIELDS if not f[k]]
    if missing:
        flash(f"接口必填项未填写: {','.join(missing)}")
        return back
    if not (f["areaid"].isdigit() and len(f["areaid"]) == 18):
        flash("areaid 必须是18位数字区域码")
        return back
    if f["sitetype"] not in ("1", "2"):
        flash("sitetype 只能选 1=室内 / 2=户外")
        return back
    if not (f["registerphone"].isdigit() and 7 <= len(f["registerphone"]) <= 15):
        flash("登记人电话必须是7-15位数字")
        return back
    for k in ("gisp_x", "gisp_y"):
        try:
            float(f[k])
        except ValueError:
            flash(f"{k} 必须是数字坐标")
            return back

    # 选填项空值规范化为 NULL
    housecode = f["housecode"] or None
    houseaddr = f["houseaddr"] or None

    with gc.db_conn() as c:
        # 兼容所有SQLite版本的UPSERT：先UPDATE，没更新到行再INSERT
        # (旧版SQLite<3.24不支持 ON CONFLICT DO UPDATE 语法)
        cur = c.execute("""UPDATE gov_device_location SET
            areaid=?, place=?, gisp_x=?, gisp_y=?, sitetype=?,
            registerperson=?, registerphone=?, housecode=?, houseaddr=?,
            update_time=? WHERE sn=?""",
            (f["areaid"], f["place"], f["gisp_x"], f["gisp_y"], f["sitetype"],
             f["registerperson"], f["registerphone"], housecode, houseaddr,
             gc.now(), f["sn"]))
        if cur.rowcount == 0:
            c.execute("""INSERT INTO gov_device_location
                (sn,areaid,place,gisp_x,gisp_y,sitetype,registerperson,
                 registerphone,housecode,houseaddr,update_time)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (f["sn"], f["areaid"], f["place"], f["gisp_x"], f["gisp_y"],
                 f["sitetype"], f["registerperson"], f["registerphone"],
                 housecode, houseaddr, gc.now()))
    flash(f"设备 {f['sn']} 位置信息已保存")
    return redirect(url_for("devices"))


@app.route("/locations/delete/<sn>", methods=["POST"])
def location_delete(sn):
    with gc.db_conn() as c:
        c.execute("DELETE FROM gov_device_location WHERE sn=?", (sn,))
    flash(f"设备 {sn} 位置信息已删除")
    return redirect(url_for("devices"))


# ================= 推送日志 =================
@app.route("/pushlog")
def pushlog():
    with gc.db_conn() as c:
        logs = [dict(r) for r in c.execute(
            "SELECT * FROM gov_push_log ORDER BY id DESC LIMIT 200")]
    return render_template("pushlog.html", logs=logs, active="pushlog")


# ================= 本地闭环测试：模拟大数据平台 =================
@app.route("/mock/bigdata", methods=["POST"])
def mock_bigdata():
    """本地测试用: 模拟龙华平台 ai_eventSend/query 的返回格式"""
    return jsonify({"return_code": "1", "return_tips": "成功",
                    "return_info": "MOCK入库成功 id=TEST0001"})


if __name__ == "__main__":
    gc.init_db()
    print("[WEB] 管理界面: http://127.0.0.1:5000")
    print("[WEB] 模拟大数据平台: POST http://127.0.0.1:5000/mock/bigdata")
    app.run(host="0.0.0.0", port=5000)
