from pydantic import BaseModel

class JobPosition(BaseModel):
    name: str
    confidence: float