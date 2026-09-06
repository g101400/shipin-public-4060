#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频监控资源现状台账 → 视频设备运维一张图数据
- 数据源优先级：① 工程内 source_data/视频监控资源现状台账.xlsx（永久备份）② Temp 下的《视频监控资源现状台账_*.xlsx》
  （16 列标准表头，第1行表头，第2行起为数据含样例；Temp 会被系统清理，故以工程内备份为主）
- 映射为 app 的 record 结构（office/station/btype/type/lon/lat/params/photos/base）
- 输出 data.js（window.__DATA__，APK 内嵌免 fetch）与 data.json（PWA 降级）
- 经纬度为空时 id 用 名称_序号 兜底，并记录「待补录」标记（params.__noll__）
"""
import json, os, glob, datetime
import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = r"C:/Users/admin/AppData/Local/Temp"


def locate_xlsx():
    """定位台账：优先工程内永久备份，回落 Temp；都没有则明确报错（不静默失败）。"""
    local = os.path.join(HERE, "source_data", "视频监控资源现状台账.xlsx")
    if os.path.isfile(local):
        print(f"[数据源] 工程内备份: {local}")
        return local
    try:
        hits = sorted(f for f in os.listdir(TMP)
                      if "视频监控资源现状台账" in f and f.endswith(".xlsx"))
    except OSError:
        hits = []
    if hits:
        p = os.path.join(TMP, hits[0])
        print(f"[数据源] Temp 回落: {p}")
        print(f"[提示] Temp 随时被清理，建议复制到 {local}")
        return p
    raise SystemExit(
        "[致命] 未找到《视频监控资源现状台账》xlsx。\n"
        f"  请放到工程内备份路径：{local}\n"
        f"  或放到：{TMP}/1：视频监控资源现状台账_*.xlsx"
    )


XLSX = locate_xlsx()


def to_float(v):
    if v is None:
        return None
    try:
        f = float(str(v).strip().replace(",", ""))
        if abs(f) < 1e-7:
            return None
        return f
    except Exception:
        return None


def valid_ll(lon, lat):
    return lon is not None and lat is not None and 73 < lon < 136 and 3 < lat < 54


def fmt_time(v):
    if v is None:
        return ""
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.strftime("%Y-%m-%d")
    return str(v).strip()


def main():
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    ws = wb.active
    records = []
    seq = 0
    valid_ll_count = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        if len(row) < 16:
            row = list(row) + [""] * (16 - len(row))
        A, B, C, D, E, F, G, H, I, J, K, L, M, N, O, P = row[:16]
        name = (B or "").strip()
        if not name:
            continue
        seq += 1
        lon = to_float(L)
        lat = to_float(M)
        has_ll = valid_ll(lon, lat)
        if has_ll:
            valid_ll_count += 1
        office = (N or "").strip()          # 所属机构（管理主体，一级分组）
        station = (E or "").strip()         # 所属区域/河湖库/水利工程名称（二级）
        btype = (I or "").strip()           # 摄像机类型（设备类型维度）
        jtime = fmt_time(J)
        params = {
            "序号": (A if A is not None else ""),
            "建设改造类型": (C or "").strip(),
            "建设改造内容": (D or "").strip(),
            "所属区域/河湖库/水利工程名称": station,
            "行政区域": (F or "").strip(),
            "设备厂商": (G or "").strip(),
            "设备型号": (H or "").strip(),
            "摄像机类型": btype,
            "安装时间": jtime,
            "安装地址": (K or "").strip(),
            "所属机构": office,
            "资源归属": (O or "").strip(),
            "监控内容": (P or "").strip(),
        }
        if not has_ll:
            params["__noll__"] = "坐标待补录"   # 地图不标，列表可查
        rid = (f"{name}_{lon:.5f}_{lat:.5f}") if has_ll else f"{name}_{seq}"
        rec = {
            "id": rid,
            "name": name,
            "type": ((station + "--" + btype) if (station and btype) else (station or btype)),
            "office": office,
            "station": station,
            "btype": btype,
            "lon": lon,
            "lat": lat,
            "params": params,
            "photos": [],
            "description": (D or "").strip(),
            "base": True,
        }
        records.append(rec)

    payload = {"generated": True, "count": len(records), "features": records}
    with open(os.path.join(HERE, "data.js"), "w", encoding="utf-8") as f:
        f.write("window.__DATA__ = " + json.dumps(payload, ensure_ascii=False, indent=1))
    with open(os.path.join(HERE, "data.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    offices = sorted(set(r["office"] for r in records if r["office"]))
    btypes = sorted(set(r["btype"] for r in records if r["btype"]))
    stations = sorted(set(r["station"] for r in records if r["station"]))
    print(f"总记录: {len(records)}")
    print(f"有效坐标: {valid_ll_count}（{100*valid_ll_count/max(len(records),1):.1f}%）| 待补录坐标: {len(records)-valid_ll_count}")
    print(f"office({len(offices)}): {offices}")
    print(f"btype({len(btypes)}): {btypes}")
    print(f"station({len(stations)}): {stations[:30]}")
    print("→ 写入 data.js / data.json 完成")


if __name__ == "__main__":
    main()
