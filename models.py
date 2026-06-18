# models.py
from pydantic import BaseModel, Field
from typing import List, Optional, Union

class QuestionModel(BaseModel):
    type: str
    topic: str
    concept_capsule: str = Field(..., description="A short, deep explanation of the core GATE concept.")
    mermaid_diagram_code: Optional[str] = Field(None, description="Mermaid.js code for flowchart/diagram. Return ONLY the graph code, no markdown ticks.")
    question: str
    A: Optional[str] = None
    B: Optional[str] = None
    C: Optional[str] = None
    D: Optional[str] = None
    EXP: str = Field(..., description="Step-by-step explanation")
    ANS: Union[str, List[str]]