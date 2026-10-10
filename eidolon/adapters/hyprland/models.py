from pydantic import BaseModel
from typing import List, Optional, Dict

class Mode(BaseModel):
    resolution: str
    refresh_rate: float

class MonitorInfo(BaseModel):
    name: str
    active_mode: Optional[Mode] = None
    available_modes: List[Mode] = []

class Directive(BaseModel):
    raw_line: str
    line_number: int

class MonitorDirective(Directive):
    name: str
    resolution: str
    position: str
    scale: str

class BindDirective(Directive):
    variant: str
    mods: str
    key: str
    dispatcher: str
    arg: str

class ExecDirective(Directive):
    is_once: bool
    command: str

class SourceDirective(Directive):
    path: str

class UnknownDirective(Directive):
    content: str

class HyprlandConfig(BaseModel):
    variables: Dict[str, str] = {}
    monitors: List[MonitorDirective] = []
    binds: List[BindDirective] = []
    execs: List[ExecDirective] = []
    sources: List[SourceDirective] = []
    unknowns: List[UnknownDirective] = []
    raw_lines: List[str] = []
