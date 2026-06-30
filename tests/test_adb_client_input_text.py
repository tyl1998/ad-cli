import unittest

from core.adb_client import ADBClient, ADBError


class RecordingADBClient(ADBClient):
    """Mock ADB client that records all shell/run calls for inspection."""

    def __init__(self, fail_input_text=False, fail_clipboard=False):
        super().__init__()
        self.calls = []
        self.fail_input_text = fail_input_text
        self.fail_clipboard = fail_clipboard

    def shell(self, *args, timeout=10):
        self.calls.append(("shell", args, timeout))
        return ""

    def run(self, *args, timeout=10):
        self.calls.append(("run", args, timeout))
        cmd_str = " ".join(str(a) for a in args)
        if self.fail_input_text and "input text" in cmd_str:
            raise ADBError("java.lang.NullPointerException: Attempt to get length of null array")
        if self.fail_clipboard and "clipboard" in cmd_str:
            raise ADBError("No shell command implementation.")
        return ""


def _get_run_cmd(c):
    """Extract the shell command string from a run() call record.

    run() call record: ("run", ("shell", "input text '...'"), timeout)
    The actual command is the second element of the args tuple.
    """
    return c[1][1] if len(c[1]) > 1 else ""


def _find_run_calls(adb, keyword):
    """Find all run() calls whose command string contains keyword."""
    return [c for c in adb.calls if c[0] == "run" and keyword in _get_run_cmd(c)]


class ADBClientInputTextTest(unittest.TestCase):

    def test_ascii_text_uses_input_text(self):
        adb = RecordingADBClient()

        adb.input_text("hello world")

        # 应该用 input text，空格替换为 %s，单引号包裹
        run_calls = _find_run_calls(adb, "input text")
        self.assertEqual(len(run_calls), 1)
        cmd = _get_run_cmd(run_calls[0])
        self.assertIn("input text 'hello%sworld'", cmd)

    def test_unicode_tries_input_text_first(self):
        """Unicode 文本也先尝试 input text（部分设备直接支持）"""
        adb = RecordingADBClient()

        adb.input_text("中文")

        # 应该先尝试 input text
        run_calls = _find_run_calls(adb, "input text")
        self.assertEqual(len(run_calls), 1)
        self.assertIn("中文", _get_run_cmd(run_calls[0]))

    def test_unicode_falls_back_to_clipboard_when_input_text_fails(self):
        """input text 抛 NullPointerException 时，回退到剪贴板粘贴"""
        adb = RecordingADBClient(fail_input_text=True)

        adb.input_text("中文")

        # 第一次：input text 失败
        input_calls = _find_run_calls(adb, "input text")
        self.assertEqual(len(input_calls), 1)

        # 第二次：剪贴板粘贴（cmd clipboard 或 service call clipboard）
        clipboard_calls = _find_run_calls(adb, "clipboard")
        self.assertGreaterEqual(len(clipboard_calls), 1)

    def test_single_quote_in_text_is_escaped(self):
        adb = RecordingADBClient()

        adb.input_text("it's")

        run_calls = _find_run_calls(adb, "input text")
        self.assertEqual(len(run_calls), 1)
        cmd = _get_run_cmd(run_calls[0])
        # 单引号通过 '\'' 转义
        self.assertIn("it'\\''s", cmd)

    def test_special_chars_are_protected_by_single_quotes(self):
        adb = RecordingADBClient()

        adb.input_text("hello$HOME;ls")

        run_calls = _find_run_calls(adb, "input text")
        self.assertEqual(len(run_calls), 1)
        cmd = _get_run_cmd(run_calls[0])
        # 特殊字符被单引号保护，原样传递
        self.assertIn("hello$HOME;ls", cmd)

    def test_clear_text_sends_select_all_and_del(self):
        adb = RecordingADBClient()

        adb.clear_text()

        shell_calls = [c for c in adb.calls if c[0] == "shell"]
        self.assertEqual(len(shell_calls), 2)
        self.assertEqual(shell_calls[0][1], ("input", "keyevent", "278"))
        self.assertEqual(shell_calls[1][1], ("input", "keyevent", "67"))


if __name__ == "__main__":
    unittest.main()
