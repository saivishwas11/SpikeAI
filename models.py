from pydantic import BaseModel
from typing import Optional, Any

class QueryRequest(BaseModel):
    query: str
    propertyId: Optional[str] = None

class QueryResponse(BaseModel):
    answer: str
    data: Optional[Any] = None