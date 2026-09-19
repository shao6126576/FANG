from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class QuestionRequest(BaseModel):
    question: str
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None

class AnswerResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    query_time: float
    conversation_id: Optional[str] = None

class GraphQueryResult(BaseModel):
    nodes: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    paths: List[Dict[str, Any]]