#!/usr/bin/env python3
"""下載香港賽馬會「出賽馬匹資料及往績（所有賽事）」PDF。

預設讀取香港本地今天的賽馬排位頁面，找出該頁的「所有賽事」PDF連結，
下載並保存至 /DATA/YYYYMMDD_starter_all_chi.pdf。
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

PAGE_URL = "https://racing.hkjc.com/zh-hk/local/information/racecard"
PDF_PATTERN = re.compile(r"/(\d{8})_starter_all_chi\.pdf(?:$|[?#])", re.I)
USER_AGENT = "Mozilla/5.0 (compatible; HKJCRacecardDownloader/1.0)"


class RacecardLinks(HTMLParser):
    """收集賽馬排位頁上「所有賽事」PDF連結。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self._href: str | None = None
        self._text: list[str] = []
        self._all_races_label = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._text = []
            self._all_races_label = False
        elif tag.lower() == "img" and self._href is not None:
            alt = dict(attrs).get("alt") or ""
            if "所有賽事" in alt:
                self._all_races_label = True

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            label = "".join(self._text).replace(" ", "")
            href = self._href
            if ("所有賽事" in label or self._all_races_label) and "starter_all_chi.pdf" in href:
                self.links.append(urljoin(PAGE_URL, href))
            self._href = None
            self._text = []
            self._all_races_label = False


def get_bytes(url: str, timeout: int) -> tuple[bytes, str]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        return response.read(), response.headers.get("Content-Type", "")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="從香港賽馬會排位頁下載指定日期的所有賽事出賽馬匹及往績 PDF。"
    )
    parser.add_argument("--date", help="賽事日期，格式 YYYYMMDD；預設為香港今天")
    parser.add_argument("--output-dir", default="/DATA", help="保存目錄（預設：/DATA）")
    parser.add_argument("--force", action="store_true", help="覆寫已存在的同名檔案")
    parser.add_argument("--timeout", type=int, default=30, help="每次網路請求逾時秒數（預設：30）")
    args = parser.parse_args()

    try:
        if args.date:
            target_date = datetime.strptime(args.date, "%Y%m%d").date()
        else:
            target_date = datetime.now(ZoneInfo("Asia/Hong_Kong")).date()
    except ValueError:
        parser.error("--date 必須是有效日期，格式為 YYYYMMDD，例如 20261111")
    if args.timeout <= 0:
        parser.error("--timeout 必須大於 0")

    ymd = target_date.strftime("%Y%m%d")
    output_dir = Path(args.output_dir)
    output_file = output_dir / f"{ymd}_starter_all_chi.pdf"

    try:
        page_bytes, _ = get_bytes(PAGE_URL, args.timeout)
        page = page_bytes.decode("utf-8", errors="replace")
        links = RacecardLinks()
        links.feed(page)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        print(f"讀取賽馬會排位頁失敗：{exc}", file=sys.stderr)
        return 1

    matching = [link for link in links.links if (match := PDF_PATTERN.search(link)) and match.group(1) == ymd]
    if not matching:
        print(
            f"排位頁目前找不到 {ymd} 的「所有賽事」PDF。"
            "該日期可能沒有本地賽事，或賽馬會尚未發布檔案。",
            file=sys.stderr,
        )
        return 2

    if output_file.exists() and not args.force:
        print(f"檔案已存在，為免覆寫而跳過：{output_file}\n如要重新下載，請加 --force")
        return 0

    try:
        pdf_bytes, content_type = get_bytes(matching[0], args.timeout)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        print(f"下載 PDF 失敗：{exc}", file=sys.stderr)
        return 1

    if not pdf_bytes.startswith(b"%PDF-"):
        print(
            f"下載內容不是有效 PDF（Content-Type: {content_type or '未知'}），不會保存。",
            file=sys.stderr,
        )
        return 3

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        # 先寫入同一目錄的暫存檔，再原子替換，避免留下不完整的 PDF。
        fd, temp_name = tempfile.mkstemp(prefix=f".{ymd}_", suffix=".tmp", dir=output_dir)
        try:
            with os.fdopen(fd, "wb") as temp_file:
                temp_file.write(pdf_bytes)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            os.replace(temp_name, output_file)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
    except OSError as exc:
        print(f"無法寫入 {output_file}：{exc}", file=sys.stderr)
        return 1

    print(f"下載完成：{output_file}（{len(pdf_bytes):,} bytes）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
