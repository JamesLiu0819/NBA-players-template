# 用途：測試 scripts/check_guide.py 的兩個判斷函數——從 GUIDE.html 抽出檔案
# 清單(guide_paths)、跟實際檔案比對找出漏列或多列的路徑(compare)。讀 git
# 檔案清單的 project_files 會碰到檔案系統跟 git,不在這裡測。
# 可手動調整的變數：無——下面的路徑跟 HTML 片段都是為了驗證規則設計的測試案例。

import unittest

from scripts.check_guide import compare, guide_paths


class GuidePathsTest(unittest.TestCase):
    def test_extracts_paths_from_the_files_array_only(self):
        html = """
<script>
const FOLDERS = { "data": "x" };
const FILES = [
  { p: "CLAUDE.md", layer: "doc", what: "a", edit: [], kw: "" },
  { p: "src/ui/silhouettes/", layer: "ui", what: "b", edit: [], kw: "" },
];
const TASKS = [
  { want: "x", go: [{ p: "not/a/file.md", at: "y" }] },
];
</script>"""
        self.assertEqual(guide_paths(html), ["CLAUDE.md", "src/ui/silhouettes/"])


class CompareTest(unittest.TestCase):
    def test_everything_listed_and_present_reports_nothing(self):
        self.assertEqual(compare(["a.py", "b/c.json"], {"a.py", "b/c.json"}), ([], []))

    def test_reports_files_missing_from_the_guide(self):
        missing, stale = compare(["a.py"], {"a.py", "new.py"})
        self.assertEqual(missing, ["new.py"])
        self.assertEqual(stale, [])

    def test_reports_listed_files_that_no_longer_exist(self):
        missing, stale = compare(["a.py", "gone.py"], {"a.py"})
        self.assertEqual(missing, [])
        self.assertEqual(stale, ["gone.py"])

    def test_folder_entry_covers_every_file_under_it(self):
        actual = {"img/x.png", "img/y.png", "a.py"}
        self.assertEqual(compare(["img/", "a.py"], actual), ([], []))

    def test_folder_entry_with_no_files_left_is_stale(self):
        missing, stale = compare(["img/", "a.py"], {"a.py"})
        self.assertEqual(stale, ["img/"])

    def test_folder_prefix_does_not_match_a_similarly_named_file(self):
        missing, _ = compare(["img/"], {"img/x.png", "imgs.txt"})
        self.assertEqual(missing, ["imgs.txt"])


if __name__ == "__main__":
    unittest.main()
