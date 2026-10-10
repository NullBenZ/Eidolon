import pytest
from pathlib import Path
from unittest.mock import patch

from eidolon.core import handle_edit, handle_undo

@patch("eidolon.core.subprocess.run")
@patch("eidolon.core.Prompt.ask")
def test_apply_twice_undo_twice(mock_ask, mock_run, tmp_path):
    # Setup
    test_file = tmp_path / "config.txt"
    test_file.write_text("v1")
    
    # 1. Edit v1 -> v2 and apply
    def fake_editor_v2(cmd, **kwargs):
        if cmd[0] == "hyprctl":
            import subprocess
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="")
        path = Path(cmd[1])
        path.write_text("v2")
        import subprocess
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="")
        
    mock_run.side_effect = fake_editor_v2
    mock_ask.return_value = "apply"
    
    handle_edit(str(test_file))
    assert test_file.read_text() == "v2"
    
    # 2. Edit v2 -> v3 and apply
    def fake_editor_v3(cmd, **kwargs):
        if cmd[0] == "hyprctl":
            import subprocess
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="")
        path = Path(cmd[1])
        path.write_text("v3")
        import subprocess
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="")
        
    mock_run.side_effect = fake_editor_v3
    mock_ask.return_value = "a" # test short answer
    
    handle_edit(str(test_file))
    assert test_file.read_text() == "v3"
    
    # 3. Undo once (should go back to v2)
    handle_undo(str(test_file))
    assert test_file.read_text() == "v2"
    
    # 4. Undo again (should go back to v1)
    handle_undo(str(test_file))
    assert test_file.read_text() == "v1"
    
    # 5. Undo a third time (should fail because no more backups)
    with pytest.raises(SystemExit):
        handle_undo(str(test_file))
        
    # File should still be v1
    assert test_file.read_text() == "v1"


@patch("eidolon.core.Prompt.ask")
def test_empty_input_handled(mock_ask, tmp_path):
    # This just verifies that if rich somehow passed an empty string, our loop handles it,
    # though rich's choices normally block it. We test the normalize logic.
    # We will pass 'd' directly since rich.prompt validates internally.
    mock_ask.return_value = "d"
    
    test_file = tmp_path / "config.txt"
    test_file.write_text("v1")
    
    # This test just ensures 'd' is mapped to 'discard' and it successfully discards.
    with patch("eidolon.core.subprocess.run") as mock_run:
        def fake_editor(cmd, **kwargs):
            if cmd[0] == "hyprctl":
                import subprocess
                return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="")
            path = Path(cmd[1])
            path.write_text("v2")
            import subprocess
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="")
        mock_run.side_effect = fake_editor
        handle_edit(str(test_file))
        
    assert test_file.read_text() == "v1" # discarded
