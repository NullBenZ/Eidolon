from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class Label(str, Enum):
    """
    Certainty of the finding.
    """
    VERIFIED = "VERIFIED"  # proved by a real check
    LIKELY = "LIKELY"      # reasonable inference
    UNKNOWN = "UNKNOWN"    # no rule or not enough data


class Severity(str, Enum):
    """
    Severity is separate from certainty.
    """
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class Finding(BaseModel):
    """
    A single issue or consequence found by an analyzer rule.
    """
    rule_id: str
    title: str
    label: Label
    severity: Severity
    evidence: str
    recommendation: str
    source: str
    line_number: Optional[int] = None


class Report(BaseModel):
    """
    The full analysis report for a file modification.
    """
    file_path: str
    findings: List[Finding] = Field(default_factory=list)
    ai_explanation: Optional[str] = None
