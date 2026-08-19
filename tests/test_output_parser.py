"""output_files must not include the runtime pip/R prefix tree."""

from coala_runtime.runtime.file_handler import FileHandler
from coala_runtime.utils.output_parser import OutputParser


def test_parse_output_skips_coala_runtime_dir(tmp_path):
    (tmp_path / "plot.png").write_bytes(b"png")
    prefix = tmp_path / ".coala-runtime" / "pip-prefix" / "lib"
    prefix.mkdir(parents=True)
    (prefix / "METADATA").write_text("pkg")

    files, data = OutputParser.parse_output("ok", "", str(tmp_path))
    assert files == [str((tmp_path / "plot.png").resolve())]
    assert data == ""


def test_parse_output_data_when_only_runtime_files(tmp_path):
    prefix = tmp_path / ".coala-runtime" / "tmp"
    prefix.mkdir(parents=True)
    (prefix / "scratch.txt").write_text("x")

    files, data = OutputParser.parse_output("shape=(213, 11)\n", "", str(tmp_path))
    assert files == []
    assert "shape=(213, 11)" in data


def test_list_output_files_skips_coala_runtime(tmp_path):
    (tmp_path / "audit.json").write_text("{}")
    nested = tmp_path / ".coala-runtime" / "home"
    nested.mkdir(parents=True)
    (nested / "dotfile").write_text("x")

    assert FileHandler.list_output_files(str(tmp_path)) == ["audit.json"]
