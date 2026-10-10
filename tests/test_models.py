import pytest
from eidolon.models import Finding, Report, Label, Severity

def test_finding_creation():
    finding = Finding(
        rule_id="RULE-001",
        title="Test Finding",
        label=Label.VERIFIED,
        severity=Severity.WARNING,
        evidence="Found a thing",
        recommendation="Fix it",
        source="Test"
    )
    assert finding.rule_id == "RULE-001"
    assert finding.label == "VERIFIED"

def test_report_creation():
    report = Report(
        file_path="/tmp/test",
        findings=[],
        ai_explanation="Looks good"
    )
    assert report.file_path == "/tmp/test"
    assert len(report.findings) == 0
    assert report.ai_explanation == "Looks good"
