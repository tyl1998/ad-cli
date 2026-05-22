import unittest

from core.adb_client import ADBClient, ADBError


class RecordingADBClient(ADBClient):
    def __init__(self, fail_input_text=False):
        super().__init__()
        self.calls = []
        self.fail_input_text = fail_input_text

    def shell(self, *args, timeout=10):
        self.calls.append((args, timeout))
        if self.fail_input_text and args[:2] == ("input", "text"):
            raise ADBError("java.lang.NullPointerException: Attempt to get length of null array")
        return ""


class ADBClientInputTextTest(unittest.TestCase):
    def test_ascii_text_uses_input_text_with_android_escaping(self):
        adb = RecordingADBClient()

        adb.input_text("hello world")

        self.assertEqual(adb.calls, [((("input", "text", "hello%sworld")), 10)])

    def test_unicode_text_uses_clipboard_paste(self):
        adb = RecordingADBClient()

        adb.input_text("中文")

        self.assertEqual(
            adb.calls,
            [
                (("cmd", "clipboard", "set", "text", "中文"), 10),
                (("input", "keyevent", "279"), 10),
            ],
        )

    def test_input_text_null_pointer_falls_back_to_clipboard_paste(self):
        adb = RecordingADBClient(fail_input_text=True)

        adb.input_text("abc")

        self.assertEqual(
            adb.calls,
            [
                (("input", "text", "abc"), 10),
                (("cmd", "clipboard", "set", "text", "abc"), 10),
                (("input", "keyevent", "279"), 10),
            ],
        )


if __name__ == "__main__":
    unittest.main()
