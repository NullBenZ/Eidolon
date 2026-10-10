
# ---------------------------------------------------------------------------
# Contradiction check
# ---------------------------------------------------------------------------

from eidolon.ai import _is_contradiction

def test_contradiction_check():
    from eidolon.models import Finding, Label, Severity
    
    # Error finding
    f_err = Finding(
        rule_id="HYP-005", title="Executable Not Found",
        label=Label.VERIFIED, severity=Severity.ERROR,
        evidence="Command not found", recommendation="", source=""
    )
    # Warning finding
    f_warn = Finding(
        rule_id="HYP-001", title="Duplicate",
        label=Label.VERIFIED, severity=Severity.WARNING,
        evidence="duplicate", recommendation="", source=""
    )
    # Unknown finding
    f_unk = Finding(
        rule_id="HYP-007", title="Unknown",
        label=Label.UNKNOWN, severity=Severity.INFO,
        evidence="dynamic", recommendation="", source=""
    )
    
    # It should catch contradiction if there is an ERROR and meaning says "successfully"
    assert _is_contradiction("This will run successfully.", [f_err]) is True
    assert _is_contradiction("Everything works perfectly, no issue.", [f_err]) is True
    
    # It should NOT catch if it's just a warning or unknown, or if no positive words
    assert _is_contradiction("This command might fail.", [f_err]) is False
    assert _is_contradiction("This will run successfully.", [f_warn]) is False
    assert _is_contradiction("This will run successfully.", [f_unk]) is False
