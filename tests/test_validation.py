from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from coal_forecasting.pipeline import _transcode_latin1_to_utf8
from coal_forecasting.validation import ValidationError, sha256_file, validate_raw_file


class RawValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.raw_path = Path(self.temporary_directory.name) / "sample.txt"
        self.raw_path.write_bytes("MINE_ID|NAME\r\n\"0001\"|\"Niño Mine\"\r\n".encode("latin-1"))
        self.spec = {
            "bytes": self.raw_path.stat().st_size,
            "sha256": sha256_file(self.raw_path),
            "delimiter": "|",
            "encoding": "latin-1",
            "quotechar": '"',
            "columns": ["MINE_ID", "NAME"],
        }

    def test_matching_file_passes(self) -> None:
        result = validate_raw_file(self.raw_path, self.spec)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["header"], ["MINE_ID", "NAME"])

    def test_hash_mismatch_fails(self) -> None:
        self.spec["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValidationError, "SHA-256 mismatch"):
            validate_raw_file(self.raw_path, self.spec)

    def test_header_mismatch_fails(self) -> None:
        self.spec["columns"] = ["MINE_ID", "WRONG_NAME"]
        with self.assertRaisesRegex(ValidationError, "Header mismatch"):
            validate_raw_file(self.raw_path, self.spec)

    def test_latin1_transcode_preserves_control_byte_as_unicode_code_point(self) -> None:
        source = Path(self.temporary_directory.name) / "control-byte.txt"
        destination = Path(self.temporary_directory.name) / "control-byte.utf8.txt"
        source.write_bytes(b"before\x8fafter")
        _transcode_latin1_to_utf8(source, destination)
        self.assertEqual(destination.read_text(encoding="utf-8"), "before\u008fafter")

    def test_unquoted_parser_contract_rejects_wrong_delimiter_count(self) -> None:
        malformed_path = Path(self.temporary_directory.name) / "malformed.txt"
        malformed_path.write_bytes(b"A|B|C\r\n1|2\r\n")
        spec = {
            "bytes": malformed_path.stat().st_size,
            "data_rows": 1,
            "sha256": sha256_file(malformed_path),
            "delimiter": "|",
            "encoding": "latin-1",
            "quotechar": "",
            "columns": ["A", "B", "C"],
        }
        with self.assertRaisesRegex(ValidationError, "Delimiter-count mismatch"):
            validate_raw_file(malformed_path, spec)


if __name__ == "__main__":
    unittest.main()
