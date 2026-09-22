#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""低頻抓取香港賽馬會上一季本地賽果，輸出 Excel 資料庫。

預設季度為 25_26（2025/26）。腳本只保存賽果名次表，不保存派彩、圖片或競賽事件報告。
請先閱讀網站條款，並自行確認抓取頻率符合網站要求。
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE = "https://racing.hkjc.com"
RESULT_URL = BASE + "/zh-hk/local/information/localresults"
DATE_API = BASE + "/racing/information/json/DateList/LocalResults.aspx?lang=zh-hk"
COLUMNS = [
    "比賽日期", "場地", "場次", "場次編號", "班別", "路程", "場地狀況", "賽道",
    "名次", "馬號", "馬名", "騎師", "練馬師", "實際負磅", "檔位", "沿途走位",
    "完成時間", "獨贏賠率",
]


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()


def get_json_dates(session: requests.Session) -> list[dict[str, str]]:
    r = session.get(DATE_API, timeout=30)
    r.raise_for_status()
    data = r.json()
    found: list[dict[str, str]] = []

    def walk(x: Any) -> None:
        if isinstance(x, dict):
            keys = {str(k).lower(): v for k, v in x.items()}
            date = keys.get("date") or keys.get("racedate") or keys.get("meetingdate") or keys.get("key")
            if isinstance(date, str):
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}T.*", date):
                    date = datetime.strptime(date[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
                if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", date):
                    venue = keys.get("venue") or keys.get("racecourse") or ""
                    found.append({"date": date, "venue": str(venue or "")})
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(data)

    # 去除 API 可能因巢狀結構造成的重複日期；保留每個日期/場地組合。
    unique = {(d["date"], d["venue"]): d for d in found}
    return list(unique.values())


def date_to_iso(d: str) -> str:
    return datetime.strptime(d, "%d/%m/%Y").strftime("%Y/%m/%d")


def season_dates(rows: list[dict[str, str]], season: str) -> list[dict[str, str]]:
    # 25_26 代表 2025-09-01 至 2026-07-30；以賽馬季慣例取 9 月至翌年 7 月。
    a, b = season.split("_")
    start_year = 2000 + int(a)
    end_year = 2000 + int(b)
    out = []
    for x in rows:
        dt = datetime.strptime(x["date"], "%d/%m/%Y")
        if datetime(start_year, 9, 1) <= dt <= datetime(end_year, 7, 30):
            out.append(x)
    return sorted(out, key=lambda z: datetime.strptime(z["date"], "%d/%m/%Y"))


def request_html(session: requests.Session, params: dict[str, str], min_delay: float, max_delay: float,
                 retries: int = 5) -> str:
    # 每一次 HTTP 請求前都等待，並在暫時性錯誤時增加退避時間。
    time.sleep(random.uniform(min_delay, max_delay))
    for attempt in range(retries):
        try:
            r = session.get(RESULT_URL, params=params, timeout=20)
            if r.status_code == 200:
                r.encoding = r.apparent_encoding or "utf-8"
                return r.text
            if r.status_code not in (429, 500, 502, 503, 504):
                r.raise_for_status()
        except requests.RequestException:
            if attempt == retries - 1:
                raise
        time.sleep(min(300, (2 ** attempt) * random.uniform(5, 12)))
    raise RuntimeError("HTTP 重試次數用盡")


def discover_races(html: str) -> list[int]:
    soup = BeautifulSoup(html, "html.parser")
    nums = set()
    for a in soup.select('a[href*="RaceNo="]'):
        m = re.search(r"RaceNo=(\d+)", a.get("href", ""))
        if m:
            nums.add(int(m.group(1)))
    return sorted(nums) or [1]


def parse_one(html: str, date_display: str, venue: str, race_no: int) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    race_table = None
    race_number = str(race_no)
    for table in soup.select("div.race_tab > table"):
        txt = clean(table.get_text(" "))
        m = re.search(r"第\s*(\d+)\s*場\s*\((\d+)\)", txt)
        if m:
            race_table, race_number = table, m.group(2)
            break
    if race_table is None:
        raise ValueError(f"找不到第 {race_no} 場標題")

    title_text = clean(race_table.get_text(" "))
    m = re.search(r"第\s*\d+\s*場\s*\(\d+\)\s+([^場]+?)\s+-\s*(\d+)米", title_text)
    cls, distance = (m.group(1).strip(), m.group(2) + "米") if m else ("", "")
    condition = ""
    track = ""
    for tr in race_table.select("tr"):
        cells = [clean(td.get_text(" ")) for td in tr.select("td")]
        row = " | ".join(cells)
        if "場地狀況" in row and len(cells) >= 3:
            condition = cells[-1]
        if "賽道" in row and len(cells) >= 3:
            track = cells[-1]

    result_table = soup.select_one(".performance table.draggable")
    if result_table is None:
        raise ValueError(f"找不到第 {race_no} 場名次表")
    rows = []
    for tr in result_table.select("tbody tr"):
        cells = [clean(td.get_text(" ")) for td in tr.select("td")]
        if len(cells) < 12 or not re.fullmatch(r"\d+", cells[0]):
            continue
        # 名次表實際 12 欄：最後一欄為獨贏賠率；排位體重及頭馬距離不納入輸出。
        rows.append(dict(zip(COLUMNS, [
            date_display, venue, str(race_no), race_number, cls, distance, condition, track,
            cells[0], cells[1], cells[2], cells[3], cells[4], cells[5], cells[7], cells[9],
            cells[10], cells[11],
        ])))
    return rows


def init_db(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE IF NOT EXISTS results (" + ",".join(f'"{c}" TEXT' for c in COLUMNS) + ", PRIMARY KEY (\"比賽日期\",\"場地\",\"場次\",\"名次\"))")
    con.commit()
    return con


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default="25_26", help="季度，例如 25_26（預設為 2025/26）")
    ap.add_argument("--output", default="hkjc_results_25_26.xlsx")
    ap.add_argument("--db", default="hkjc_results.sqlite")
    ap.add_argument("--min-delay", type=float, default=8.0)
    ap.add_argument("--max-delay", type=float, default=20.0)
    ap.add_argument("--max-races", type=int, default=0, help="測試用；0 代表完整季度")
    ap.add_argument("--only-date", help="測試單一日期，格式 DD/MM/YYYY，例如 07/09/2025")
    args = ap.parse_args()
    if args.min_delay < 1 or args.max_delay < args.min_delay:
        ap.error("延遲參數不合法")

    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (compatible; HKJCResultsResearch/1.0)", "Accept-Language": "zh-HK,zh;q=0.9"})
    dates = season_dates(get_json_dates(s), args.season)
    if args.only_date:
        dates = [{"date": args.only_date, "venue": ""}]
    if not dates:
        raise RuntimeError(f"API 找不到季度 {args.season} 的日期；可檢查季度格式或日期清單是否已更新")
    con = init_db(Path(args.db))
    total = 0
    for meeting in dates:
        display = meeting["date"]
        iso = date_to_iso(display)
        venue = meeting["venue"]
        candidates = [venue] if venue else ["ST", "HV"]
        first = ""
        races: list[int] = []
        chosen = venue
        for candidate in candidates:
            candidate_html = request_html(s, {"racedate": iso, "Racecourse": candidate}, args.min_delay, args.max_delay)
            candidate_races = discover_races(candidate_html)
            if candidate_races != [1] or "沒有相關資料" not in clean(BeautifulSoup(candidate_html, "html.parser").get_text(" ")):
                first, races, chosen = candidate_html, candidate_races, candidate
                break
        if not first:
            print(f"跳過 {display}：ST/HV 均沒有相關賽果")
            continue
        venue = chosen
        if args.max_races:
            races = races[: max(0, args.max_races - total)]
        for n in races:
            html = first if n == 1 else request_html(s, {"racedate": iso, "RaceNo": str(n), "Racecourse": venue}, args.min_delay, args.max_delay)
            try:
                records = parse_one(html, display, venue, n)
            except Exception as e:
                print(f"跳過 {display} {venue} 第 {n} 場：{e}", file=sys.stderr)
                continue
            con.executemany("INSERT OR REPLACE INTO results VALUES (" + ",".join("?" for _ in COLUMNS) + ")", [[r[c] for c in COLUMNS] for r in records])
            con.commit()
            total += 1
            print(f"完成 {display} {venue} 第 {n} 場；目前 {total} 場")
            if args.max_races and total >= args.max_races:
                break
        if args.max_races and total >= args.max_races:
            break

    df = pd.read_sql_query('SELECT * FROM results ORDER BY 比賽日期, 場地, CAST(場次 AS INTEGER), CAST(名次 AS INTEGER)', con)
    with pd.ExcelWriter(args.output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="賽果", index=False)
        pd.DataFrame({"欄位": COLUMNS, "說明": ["來源頁面日期", "HV/ST 或 API 場地代碼", "頁面場次", "括號內場次編號", "班別", "路程", "場地狀況", "賽道", "官方名次", "馬號", "馬名", "騎師", "練馬師", "實際負磅", "檔位", "沿途走位", "完成時間", "獨贏賠率"]}).to_excel(writer, sheet_name="欄位說明", index=False)
    con.close()
    print(f"輸出完成：{args.output}；賽事 {total} 場；馬匹紀錄 {len(df)} 行")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
