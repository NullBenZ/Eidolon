import difflib

def compute_diff(original: str, edited: str, fromfile: str = "original", tofile: str = "edited") -> str:
    """
    Computes a unified diff between the original and edited strings.
    """
    original_lines = original.splitlines(keepends=True)
    edited_lines = edited.splitlines(keepends=True)
    
    diff = difflib.unified_diff(
        original_lines,
        edited_lines,
        fromfile=fromfile,
        tofile=tofile,
        n=3
    )
    return "".join(diff)
