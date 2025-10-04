# app/models.py
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime

class SaveConvRequest(BaseModel):
    """Equivalente C#: SaveConvRequest"""
    convName: str
    transcribe: str

class SaveReconstructionResponse(BaseModel):
    """Equivalente C#: SaveReconstructionResponse"""
    id: Optional[str] = None
    status: str = "OK"

class UsageInfo(BaseModel):
    """Equivalente C#: UsageInfo"""
    tokens: int = 0
    costUsd: float = 0.0

class ReconstructionResponse(BaseModel):
    """Equivalente C#: ReconstructionResponse"""
    files: List[str] = []
    reconstructedTranscript: str = ""
    usage: UsageInfo = UsageInfo()