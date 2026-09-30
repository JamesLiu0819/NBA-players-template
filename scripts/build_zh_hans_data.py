#!/usr/bin/env python3
# 用途：把 data/zh(繁體中文)整包轉成 data/zh-Hans(簡體中文),供
# server/app.py 的 DATA_FILENAMES["zh-Hans"] 讀取。繁簡中文是同一種語言、只
# 差在字形跟部分用詞,所以這裡用 OpenCC 做字元/詞彙轉換,而不是像 data/en
# 那樣整份重新翻譯——這樣兩份繁簡內容才會永遠同步,不會各自累積差異。
# 要重新產生輸出時直接重跑這支腳本即可,data/zh-Hans/ 底下的檔案都是建置產物,
# 不要手改(跟 data/players.json 的規則一樣,見 CLAUDE.md)。
# 用到 opencc-python-reimplemented,只有跑這支腳本時才需要,不是 server 執行期
# 依賴,所以沒有加進 server/requirements.txt(pip install opencc-python-reimplemented)。
# 轉換設定用 "tw2sp"(繁體台灣用語 → 簡體並轉換常用詞彙,例如 軟體→软件),
# 比純字元轉換的 "t2s" 更接近簡體中文使用者習慣的用詞。
"""Converts data/zh/*.json (Traditional Chinese) into data/zh-Hans/*.json
(Simplified Chinese) via OpenCC script/phrase conversion.

Usage:
    python3 scripts/build_zh_hans_data.py
"""
import json
import sys
from pathlib import Path

from opencc import OpenCC

ROOT = Path(__file__).resolve().parents[1]

SOURCE_DIR = ROOT / "data" / "zh"
TARGET_DIR = ROOT / "data" / "zh-Hans"

FILENAME_MAP = {
    "題庫.json": "题库.json",
    "技能.json": "技能.json",
    "原型.json": "原型.json",
    "球員.json": "球员.json",
    "歷史球員.json": "历史球员.json",
}

converter = OpenCC("tw2sp")


def convert_value(value):
    if isinstance(value, str):
        return converter.convert(value)
    if isinstance(value, dict):
        return {key: convert_value(v) for key, v in value.items()}
    if isinstance(value, list):
        return [convert_value(v) for v in value]
    return value


def main():
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    for source_name, target_name in FILENAME_MAP.items():
        source_path = SOURCE_DIR / source_name
        with open(source_path, encoding="utf-8") as f:
            data = json.load(f)
        converted = convert_value(data)
        target_path = TARGET_DIR / target_name
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(converted, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"{source_path.relative_to(ROOT)} -> {target_path.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
