#!/usr/bin/env python3
# 用途：檢查 GUIDE.html(專案導覽)裡的檔案清單 FILES,跟專案裡實際存在的檔案
# 有沒有對不上——有檔案沒被列進導覽,或導覽列了已經不存在的檔案,就印出來
# 並以非 0 結束。新增、刪除、搬動檔案之後執行一次。只在本機手動執行,不是
# engine 的一部分,網站執行時不會跑。
# 可手動調整的變數：無。導覽裡路徑結尾是 "/" 的項目代表「整個資料夾當一筆」,
# 該資料夾底下的檔案都算已列入。
"""Report files missing from, or stale in, GUIDE.html's FILES list."""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "GUIDE.html"
PATH_PATTERN = re.compile(r'\{\s*p:\s*"([^"]+)"')


def guide_paths(html):
    """Paths listed in the FILES array of the guide's script block."""
    files_block = html.split("const FILES = [", 1)[1].split("\n];", 1)[0]
    return PATH_PATTERN.findall(files_block)


def compare(listed, actual):
    """Return (missing, stale): actual files the guide doesn't cover, and
    listed paths that no longer exist. A listed path ending in "/" covers
    every actual file under that folder."""
    folders = [p for p in listed if p.endswith("/")]
    exact = {p for p in listed if not p.endswith("/")}
    missing = sorted(
        f for f in actual
        if f not in exact and not any(f.startswith(folder) for folder in folders)
    )
    stale = sorted(
        [p for p in exact if p not in actual]
        + [folder for folder in folders if not any(f.startswith(folder) for f in actual)]
    )
    return missing, stale


def project_files():
    """Tracked plus untracked-but-not-ignored files, as repo-relative paths."""
    output = subprocess.run(
        ["git", "-c", "core.quotepath=false", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return {line for line in output.splitlines() if line and (ROOT / line).exists()}


def main():
    listed = guide_paths(GUIDE.read_text(encoding="utf-8"))
    missing, stale = compare(listed, project_files())
    for path in missing:
        print(f"沒列進導覽：{path}")
    for path in stale:
        print(f"導覽裡有、實際不存在：{path}")
    if missing or stale:
        sys.exit(1)
    print(f"導覽的檔案清單跟專案一致（{len(listed)} 筆）。")


if __name__ == "__main__":
    main()
