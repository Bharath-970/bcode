# tests/test_git.py
from pathlib import Path
from bcode.git import _parse_diff_text, DiffResult, ChangedFile

FIXTURES = Path(__file__).parent / "fixtures" / "diffs"

def test_parses_clean_diff():
    text = (FIXTURES / "clean.diff").read_text()
    result = _parse_diff_text(text, Path("."), commit_counts=None)
    assert len(result.files) == 1
    assert result.files[0].path == Path("src/auth.py")
    assert any("user.last_login" in line for line in result.files[0].added_lines)

def test_parses_added_lines_only():
    text = (FIXTURES / "hallucinated_import.diff").read_text()
    result = _parse_diff_text(text, Path("."), commit_counts=None)
    assert len(result.files) == 1
    added = result.files[0].added_lines
    assert "import jose" in added
    assert "from jose import jwt" in added

def test_parses_multi_file():
    text = (FIXTURES / "multi_file.diff").read_text()
    result = _parse_diff_text(text, Path("."), commit_counts=None)
    assert len(result.files) == 2
    paths = {f.path for f in result.files}
    assert Path("src/auth.py") in paths
    assert Path("src/utils.py") in paths

def test_commit_count_applied():
    text = (FIXTURES / "multi_file.diff").read_text()
    counts = {"src/auth.py": 4, "src/utils.py": 1}
    result = _parse_diff_text(text, Path("."), commit_counts=counts)
    auth_file = next(f for f in result.files if f.path == Path("src/auth.py"))
    assert auth_file.commit_count == 4

def test_commit_count_zero_when_no_counts():
    text = (FIXTURES / "clean.diff").read_text()
    result = _parse_diff_text(text, Path("."), commit_counts=None)
    assert result.files[0].commit_count == 0
