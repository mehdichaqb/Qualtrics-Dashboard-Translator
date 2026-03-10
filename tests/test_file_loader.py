"""Tests for file loading."""

import io
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from processor.file_loader import load_file, detect_encoding


class TestLoadFile:
    """Test CSV and XLSX loading."""

    def test_load_csv_from_bytes(self):
        csv_content = "col1,col2\nA,B\nC,D"
        stream = io.BytesIO(csv_content.encode("utf-8"))
        df = load_file(stream, file_name="test.csv")
        assert len(df) == 2
        assert list(df.columns) == ["col1", "col2"]
        assert df.iloc[0]["col1"] == "A"

    def test_load_csv_with_bom(self):
        csv_content = "\ufeffcol1,col2\nA,B"
        stream = io.BytesIO(csv_content.encode("utf-8-sig"))
        df = load_file(stream, file_name="test.csv")
        assert "col1" in df.columns

    def test_load_csv_with_quotes_and_commas(self):
        csv_content = 'col1,col2\n"Hello, World","She said ""hi"""\nA,B'
        stream = io.BytesIO(csv_content.encode("utf-8"))
        df = load_file(stream, file_name="test.csv")
        assert len(df) == 2
        assert df.iloc[0]["col1"] == "Hello, World"
        assert df.iloc[0]["col2"] == 'She said "hi"'

    def test_load_csv_nan_as_string(self):
        csv_content = "col1,col2\nNaN,\nNA,"
        stream = io.BytesIO(csv_content.encode("utf-8"))
        df = load_file(stream, file_name="test.csv")
        # NaN should be kept as string "NaN", not float
        assert df.iloc[0]["col1"] == "NaN"
        assert df.iloc[0]["col2"] == ""

    def test_load_from_path(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("a,b\n1,2\n3,4", encoding="utf-8")
        df = load_file(str(csv_file))
        assert len(df) == 2

    def test_unsupported_extension(self):
        stream = io.BytesIO(b"data")
        with pytest.raises(ValueError, match="Unsupported"):
            load_file(stream, file_name="test.json")

    def test_missing_filename_for_stream(self):
        stream = io.BytesIO(b"data")
        with pytest.raises(ValueError, match="file_name"):
            load_file(stream)

    def test_load_xlsx(self, tmp_path):
        """Test XLSX loading."""
        xlsx_file = tmp_path / "test.xlsx"
        df_orig = pd.DataFrame({"A": ["1", "2"], "B": ["3", "4"]})
        df_orig.to_excel(str(xlsx_file), index=False, engine="openpyxl")

        df = load_file(str(xlsx_file))
        assert len(df) == 2
        assert list(df.columns) == ["A", "B"]


class TestDetectEncoding:
    """Test encoding detection."""

    def test_utf8(self):
        text = "Hello café"
        enc = detect_encoding(text.encode("utf-8"))
        assert "utf" in enc.lower()

    def test_ascii(self):
        enc = detect_encoding(b"Hello world")
        # chardet may return ascii, we normalize to utf-8
        assert enc in ("utf-8", "ascii")

    def test_latin1(self):
        text = "Héllo café"
        raw = text.encode("latin-1")
        enc = detect_encoding(raw)
        # Should detect some encoding
        assert enc is not None
