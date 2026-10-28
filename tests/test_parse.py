"""Log parser tests. No Keil installation needed: fixtures are captured log text."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from keil_build import parse_log  # noqa: E402

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"


def load(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


class ParseTest(unittest.TestCase):
    def test_warning_has_file_and_line(self):
        result = parse_log(load("keil_warn.log"))
        self.assertEqual(result["warnings"], 2)
        self.assertEqual(result["errors"], 0)
        first = result["diagnostics"][0]
        self.assertEqual(first["level"], "warning")
        self.assertEqual(first["file"], "../../../device/dev_spi_flash.c")
        self.assertEqual(first["line"], 106)
        self.assertIn("LOG_WARN", first["msg"])
        self.assertFalse(result["clean"])

    def test_error_is_parsed(self):
        result = parse_log(load("keil_error.log"))
        self.assertEqual(result["errors"], 1)
        self.assertEqual(result["warnings"], 0)
        self.assertEqual(result["diagnostics"][0]["line"], 58)
        self.assertIn("LINE_MAX", result["diagnostics"][0]["msg"])

    def test_sizes_and_ram(self):
        result = parse_log(load("keil_short.log"))
        self.assertEqual(result["sizes"], [172944, 8564, 284, 49500])
        self.assertEqual(result["sizes"][2] + result["sizes"][3], 49784)

    def test_missing_size_line(self):
        result = parse_log("Rebuild target 'template'\n0 Error(s), 0 Warning(s)\n")
        self.assertIsNone(result["sizes"])
        self.assertTrue(result["clean"])

    def test_clean_build_flag(self):
        self.assertTrue(parse_log(load("keil_short.log"))["clean"] is False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
