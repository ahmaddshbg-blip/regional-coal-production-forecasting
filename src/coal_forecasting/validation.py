"""Raw-file and checkpoint validation helpers."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any


class ValidationError(RuntimeError):
    """Raised when source data violates the frozen contract."""


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_delimited_header(
    path: str | Path,
    *,
    encoding: str,
    delimiter: str,
    quotechar: str = '"',
) -> list[str]:
    with Path(path).open("r", encoding=encoding, newline="") as handle:
        first_line = handle.readline()
    if not first_line:
        raise ValidationError(f"Raw file is empty: {Path(path).name}")
    if quotechar:
        return next(csv.reader([first_line], delimiter=delimiter, quotechar=quotechar))
    return next(csv.reader([first_line], delimiter=delimiter, quoting=csv.QUOTE_NONE))


def inspect_unquoted_delimited_file(
    path: str | Path,
    *,
    delimiter: str,
    expected_columns: int,
) -> dict[str, Any]:
    """Hash a file and verify fixed-width rows when quote parsing is disabled."""
    delimiter_bytes = delimiter.encode("ascii")
    expected_delimiters = expected_columns - 1
    digest = hashlib.sha256()
    line_count = 0
    malformed_lines: list[int] = []

    with Path(path).open("rb") as handle:
        for line_count, line in enumerate(handle, start=1):
            digest.update(line)
            if line.count(delimiter_bytes) != expected_delimiters and len(malformed_lines) < 5:
                malformed_lines.append(line_count)

    return {
        "sha256": digest.hexdigest(),
        "data_rows": max(line_count - 1, 0),
        "malformed_lines": malformed_lines,
    }


def validate_raw_file(path: str | Path, spec: dict[str, Any]) -> dict[str, Any]:
    raw_path = Path(path)
    if not raw_path.is_file():
        raise FileNotFoundError(
            f"Required raw file not found: {raw_path}. "
            "Download it manually from the documented MSHA source."
        )

    observed_bytes = raw_path.stat().st_size
    expected_bytes = int(spec["bytes"])
    if observed_bytes != expected_bytes:
        raise ValidationError(
            f"Size mismatch for {raw_path.name}: expected {expected_bytes}, "
            f"observed {observed_bytes} bytes"
        )

    expected_header = list(spec["columns"])
    observed_header = read_delimited_header(
        raw_path,
        encoding=spec["encoding"],
        delimiter=spec["delimiter"],
        quotechar=spec.get("quotechar", '"'),
    )
    if observed_header != expected_header:
        raise ValidationError(
            f"Header mismatch for {raw_path.name}. "
            f"Expected {expected_header}; observed {observed_header}"
        )

    if not spec.get("quotechar", '"'):
        inspection = inspect_unquoted_delimited_file(
            raw_path,
            delimiter=spec["delimiter"],
            expected_columns=len(expected_header),
        )
        if inspection["malformed_lines"]:
            raise ValidationError(
                f"Delimiter-count mismatch in {raw_path.name} on line(s): "
                + ", ".join(str(line) for line in inspection["malformed_lines"])
            )
        if "data_rows" in spec and inspection["data_rows"] != int(spec["data_rows"]):
            raise ValidationError(
                f"Row-count mismatch for {raw_path.name}: expected {spec['data_rows']}, "
                f"observed {inspection['data_rows']}"
            )
        observed_sha256 = inspection["sha256"]
        observed_data_rows: int | None = inspection["data_rows"]
    else:
        observed_sha256 = sha256_file(raw_path)
        observed_data_rows = None
    expected_sha256 = spec["sha256"].lower()
    if observed_sha256.lower() != expected_sha256:
        raise ValidationError(
            f"SHA-256 mismatch for {raw_path.name}: expected {expected_sha256}, "
            f"observed {observed_sha256}"
        )

    return {
        "filename": raw_path.name,
        "bytes": observed_bytes,
        "sha256": observed_sha256,
        "header": observed_header,
        "data_rows": observed_data_rows,
        "status": "passed",
    }
