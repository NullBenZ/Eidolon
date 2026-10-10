import pytest
from eidolon.diff import compute_diff

def test_compute_diff():
    original = "line1\nline2\nline3\n"
    edited = "line1\nline2 changed\nline3\n"
    
    diff = compute_diff(original, edited)
    
    assert "--- original" in diff
    assert "+++ edited" in diff
    assert "-line2\n" in diff
    assert "+line2 changed\n" in diff

def test_compute_diff_no_changes():
    original = "line1\nline2\n"
    edited = "line1\nline2\n"
    
    diff = compute_diff(original, edited)
    assert diff == ""
