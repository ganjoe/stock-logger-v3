from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

class ItemType(Enum):
    REQUIREMENT = "REQ"
    SPECIFICATION = "SPEC"
    TEST_CASE = "TEST"
    UNKNOWN = "UNKNOWN"

@dataclass
class DocItem:
    uid: str
    category: str
    title: str
    description: str
    covered_by: str # Comma-separated IDs or Links
    
    @property
    def item_type(self) -> ItemType:
        if self.uid.startswith("F-"): return ItemType.REQUIREMENT
        if self.uid.startswith("S-"): return ItemType.SPECIFICATION
        if self.uid.startswith("T") or self.uid.startswith("TC-"): return ItemType.TEST_CASE
        return ItemType.UNKNOWN
