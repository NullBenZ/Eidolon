import os
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from eidolon.core import get_file_hash, backup_file, resolve_target, handle_edit, handle_undo


def test_get_file_hash(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello world")
    
    # known hash of "hello world"
    # echo -n "hello world" | sha256sum
    expected_hash = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
    assert get_file_hash(test_file) == expected_hash


def test_backup_file(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello world")
    
    backup_path = backup_file(test_file)
    assert backup_path.exists()
    assert backup_path.read_text() == "hello world"
    assert backup_path.name.startswith("test.txt.")
    assert backup_path.name.endswith(".bak")


@patch("eidolon.core.Confirm.ask")
def test_resolve_target_symlink_confirm(mock_confirm, tmp_path):
    real_file = tmp_path / "real.txt"
    real_file.write_text("real content")
    symlink = tmp_path / "link.txt"
    symlink.symlink_to(real_file)
    
    mock_confirm.return_value = True
    resolved = resolve_target(symlink)
    assert resolved == real_file


@patch("eidolon.core.Confirm.ask")
def test_resolve_target_symlink_abort(mock_confirm, tmp_path):
    real_file = tmp_path / "real.txt"
    real_file.write_text("real content")
    symlink = tmp_path / "link.txt"
    symlink.symlink_to(real_file)
    
    mock_confirm.return_value = False
    with pytest.raises(SystemExit):
        resolve_target(symlink)


@patch("eidolon.core.Prompt.ask")
@patch("eidolon.core.subprocess.run")
def test_handle_edit_apply(mock_run, mock_prompt, tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("original content")
    
    def fake_nano(cmd, **kwargs):
        if cmd[0] == "hyprctl":
            import subprocess
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="")
        path = Path(cmd[1])
        path.write_text("edited content")
        import subprocess
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="")
        
    mock_run.side_effect = fake_nano
    mock_prompt.return_value = "apply"
    
    handle_edit(str(test_file))
    
    assert test_file.read_text() == "edited content"
    # check if backup was created
    backups = list(tmp_path.glob("test.txt.*.bak"))
    assert len(backups) == 1
    assert backups[0].read_text() == "original content"


@patch("eidolon.core.Prompt.ask")
@patch("eidolon.core.subprocess.run")
def test_handle_edit_discard(mock_run, mock_prompt, tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("original content")
    
    def fake_nano(cmd, **kwargs):
        if cmd[0] == "hyprctl":
            import subprocess
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="")
        path = Path(cmd[1])
        path.write_text("edited content")
        import subprocess
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="")
        
    mock_run.side_effect = fake_nano
    mock_prompt.return_value = "discard"
    
    handle_edit(str(test_file))
    
    # Original should be untouched
    assert test_file.read_text() == "original content"


@patch("eidolon.core.Prompt.ask")
@patch("eidolon.core.subprocess.run")
def test_handle_edit_conflict(mock_run, mock_prompt, tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("original content")
    
    def fake_nano(cmd, **kwargs):
        if cmd[0] == "hyprctl":
            import subprocess
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="")
        path = Path(cmd[1])
        path.write_text("edited content")
        # Simulate someone modifying the original file while editing
        test_file.write_text("someone else changed this")
        import subprocess
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="")
        
    mock_run.side_effect = fake_nano
    mock_prompt.return_value = "apply"
    
    with pytest.raises(SystemExit):
        handle_edit(str(test_file))
        
    # Should not overwrite with "edited content", it remains the modified text
    assert test_file.read_text() == "someone else changed this"


def test_handle_undo(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("current state")
    
    # create a backup file
    backup_file = tmp_path / "test.txt.20261010_120000.bak"
    backup_file.write_text("previous state")
    
    handle_undo(str(test_file))
    
    assert test_file.read_text() == "previous state"
    
    # Check if a .pre-undo of "current state" was created
    pre_undos = sorted(tmp_path.glob("test.txt.*.pre-undo"))
    assert len(pre_undos) == 1
    assert pre_undos[0].read_text() == "current state"
    
    # Check if the backup was marked as .restored
    restored = sorted(tmp_path.glob("test.txt.*.restored"))
    assert len(restored) == 1
    assert restored[0].read_text() == "previous state"
    
    # The original .bak should be gone
    baks = sorted(tmp_path.glob("test.txt.*.bak"))
    assert len(baks) == 0

def test_handle_undo_multiple(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("state 3")
    
    b1 = tmp_path / "test.txt.1.bak"
    b1.write_text("state 1")
    
    b2 = tmp_path / "test.txt.2.bak"
    b2.write_text("state 2")
    
    # First undo restores state 2
    handle_undo(str(test_file))
    assert test_file.read_text() == "state 2"
    assert not b2.exists()
    assert b2.with_suffix(".restored").exists()
    
    # Second undo restores state 1
    handle_undo(str(test_file))
    assert test_file.read_text() == "state 1"
    assert not b1.exists()
    assert b1.with_suffix(".restored").exists()
    
    # Third undo fails
    with pytest.raises(SystemExit):
        handle_undo(str(test_file))
