#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_index.py — 掃描 tradinginfo 資料夾內的 HTML 研究報告,
更新 index.html 內嵌的報告清單(<script id="reports-data">)。

用法:
    python build_index.py              # 更新 index.html
    python build_index.py --check      # 只檢查,不寫入(CI 用,有差異回傳 1)
    python build_index.py --dir <path> # 指定資料夾

規則:
  * 已存在於清單中的報告 → 只自動更新 file/bytes,其餘欄位(name/summary/tags/…)保留人工內容。
  * 新增的 HTML → 先讀 head 的 report-* meta;讀不到才用檔名與 <title>/<h1> 推導,
    並在終端列出「需人工補齊」的欄位。絕不編造摘要。
  * 檔案已刪除 → 從清單移除並提示。
"""

import argparse
import datetime as _dt
import html
import json
import os
import re
import sys

INDEX = "index.html"
BLOCK_RE = re.compile(
    r'(<script id="reports-data" type="application/json">)(.*?)(</script>)', re.S
)
BUILD_META_RE = re.compile(r'(<meta name="index-build" content=")([^"]*)(">)')

# 檔名 → 類型的後備推導(僅在沒有 meta 時使用)
TYPE_HINTS = [
    (re.compile(r"supply_chain|_chain_|產業鏈"), "chain"),
    (re.compile(r"^commodity_"), "commodity"),
    (re.compile(r"^(tw|us|hk|cn|jp)_"), "stock"),
]
MARKET_BY_SUFFIX = {".TW": "上市", ".TWO": "上櫃", ".TWE": "興櫃"}
FIELDS = ["file", "type", "code", "ticker", "name", "market", "sector",
          "date", "summary", "tags", "bytes"]


def strip_tags(s: str) -> str:
    s = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def read_head(path: str) -> str:
    """只讀檔頭一段,避免把 800KB 報告整份載入。"""
    with open(path, encoding="utf-8", errors="ignore") as fh:
        return fh.read(120_000)


def parse_metas(head: str) -> dict:
    out = {}
    for m in re.finditer(r"<meta\s+[^>]*>", head, re.I):
        tag = m.group(0)
        n = re.search(r'name\s*=\s*["\']report-([a-z]+)["\']', tag, re.I)
        c = re.search(r'content\s*=\s*["\']([^"\']*)["\']', tag, re.I)
        if n and c:
            out[n.group(1).lower()] = html.unescape(c.group(1)).strip()
    return out


def date_from_name(fn: str):
    m = re.search(r"_(\d{2})(\d{2})(\d{2})\.html?$", fn)
    if m:
        return "20%s-%s-%s" % m.groups()
    return None


def code_from_name(fn: str):
    """從檔名取股票代號。刻意排除結尾的 _YYMMDD 日期段,避免把日期當成代號。"""
    base = re.sub(r"_\d{6}(?=\.html?$)", "", fn, flags=re.I)   # 先砍掉結尾日期
    m = re.search(r"[_-](\d{4,6})(?=[_.-])", base)
    return m.group(1) if m else ""


def derive(path: str, fn: str) -> dict:
    head = read_head(path)
    meta = parse_metas(head)

    t = meta.get("type")
    if not t:
        t = next((v for rx, v in TYPE_HINTS if rx.search(fn)), "stock")

    # meta 明確寫了 report-code(即使是空字串)就以它為準;沒寫才從檔名推導
    code = meta["code"] if "code" in meta else code_from_name(fn)

    name = meta.get("name")
    if not name:
        m = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", head)
        if m:
            name = strip_tags(m.group(1))[:40]
        else:
            m = re.search(r"<title>([^<]*)</title>", head)
            name = re.split(r"[—|｜|]", m.group(1))[0].strip() if m else fn
        if code and code in name:
            name = name.replace(code, "").strip(" .·-—")

    ticker = meta.get("ticker", "")
    market = meta.get("market", "")
    if not (ticker and market):
        m = re.search(r"\b(\d{4,6})\.(TWO?|TWE)\b", head)
        if m:
            ticker = ticker or m.group(0)
            market = market or MARKET_BY_SUFFIX.get("." + m.group(2), "")

    date = meta.get("date") or date_from_name(fn)
    if not date:
        date = _dt.date.fromtimestamp(os.path.getmtime(path)).isoformat()

    tags = meta.get("tags", "")
    tags = [x.strip() for x in re.split(r"[,、,]", tags) if x.strip()] if tags else []

    return {
        "file": fn, "type": t, "code": code, "ticker": ticker, "name": name,
        "market": market, "sector": meta.get("sector", ""), "date": date,
        "summary": meta.get("summary", ""), "tags": tags,
        "bytes": os.path.getsize(path),
    }


def order(rec: dict) -> dict:
    return {k: rec.get(k, "" if k != "tags" else []) for k in FIELDS}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--check", action="store_true", help="只檢查,不寫入")
    args = ap.parse_args()

    root = args.dir
    idx_path = os.path.join(root, INDEX)
    if not os.path.exists(idx_path):
        print("找不到 %s" % idx_path, file=sys.stderr)
        return 2

    src = open(idx_path, encoding="utf-8").read()
    m = BLOCK_RE.search(src)
    if not m:
        print('index.html 內找不到 <script id="reports-data"> 區塊', file=sys.stderr)
        return 2

    existing = {r["file"]: r for r in json.loads(m.group(2))}

    files = sorted(f for f in os.listdir(root)
                   if f.lower().endswith((".html", ".htm")) and f != INDEX)

    records, added, removed, incomplete = [], [], [], []

    for fn in files:
        path = os.path.join(root, fn)
        if fn in existing:                       # 既有 → 保留人工欄位
            rec = dict(existing[fn])
            rec["bytes"] = os.path.getsize(path)
        else:                                    # 新增 → 自動推導
            rec = derive(path, fn)
            added.append(fn)
            miss = [k for k in ("summary", "name", "date") if not rec.get(k)]
            if not rec.get("tags"):
                miss.append("tags")
            if miss:
                incomplete.append((fn, miss))
        records.append(order(rec))

    for fn in existing:
        if fn not in files:
            removed.append(fn)

    records.sort(key=lambda r: (r.get("date") or "", r.get("code") or ""), reverse=True)

    payload = json.dumps(records, ensure_ascii=False, indent=2)
    today = _dt.date.today().isoformat()
    out = src[:m.start(2)] + "\n" + payload + "\n" + src[m.end(2):]
    out = BUILD_META_RE.sub(lambda mm: mm.group(1) + today + mm.group(3), out, count=1)

    changed = out != src
    if args.check:
        print("有差異,請執行 python build_index.py" if changed else "index.html 已是最新")
        return 1 if changed else 0

    if changed:
        open(idx_path, "w", encoding="utf-8", newline="\n").write(out)

    print("index.html %s — 共 %d 份報告" % ("已更新" if changed else "無變更", len(records)))
    for fn in added:
        print("  + 新增  %s" % fn)
    for fn in removed:
        print("  - 移除  %s" % fn)
    for fn, miss in incomplete:
        print("  ! 待補  %s → %s（請在報告 head 加 report-* meta,或直接編輯 index.html 的清單）"
              % (fn, "、".join(miss)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
