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


# --- a compiler diagnostic is not a file path ---------------------------------------------


def test_a_long_diagnostic_line_mentioning_output_does_not_abort_the_parse(tmp_path):
    """An R package build printed `/output/.coala-runtime/.../SparseMatrix.h:1040:66: required
    from ‘void Eigen::internal::set_from_triplets(...)’ …` to stderr. The `/output/(.+)` pattern
    captured the whole line, `Path.resolve()` raised ENAMETOOLONG, and only ValueError was
    caught — the exception replaced the entire result (exit_code -1, logs gone). The compile's
    real outcome was lost; on retry it installed fine.
    """
    (tmp_path / "result.csv").write_text("a,b\n")
    # The directory chain must exist: the kernel walks the path and reports the first missing
    # component as ENOENT, which is_file() ignores. In production the R library was installed
    # there, so the walk reached the 300-character "file name" and got ENAMETOOLONG instead.
    (tmp_path / ".coala-runtime/R/library/RcppEigen/include/Eigen/src/SparseCore").mkdir(parents=True)
    diag = ("/output/.coala-runtime/R/library/RcppEigen/include/Eigen/src/SparseCore/"
            "SparseMatrix.h:1040:66:   required from ‘void Eigen::internal::set_from_triplets("
            + "const InputIterator&, " * 20 + "…)’")
    assert len(diag) > 255
    files, data = OutputParser.parse_output("", diag, str(tmp_path))
    assert files == [str((tmp_path / "result.csv").resolve())]
    assert data == ""


def test_a_real_output_path_reference_is_still_picked_up(tmp_path):
    sub = tmp_path / "plots"
    sub.mkdir()
    (sub / "fig.png").write_bytes(b"png")
    files, _ = OutputParser.parse_output("Saved to: /output/plots/fig.png done", "", str(tmp_path))
    assert str((sub / "fig.png").resolve()) in files
