import subprocess
import sys
import pytest

def test_cli_help():
    result = subprocess.run([sys.executable, "-m", "eidolon.cli", "-h"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "EIDOLON: A Linux config impact analyzer" in result.stdout

def test_cli_edit():
    result = subprocess.run([sys.executable, "-m", "eidolon.cli", "edit", "config.txt"], capture_output=True, text=True)
    assert result.returncode == 1
    assert "Error: File config.txt does not exist." in result.stdout
