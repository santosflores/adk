import datetime
import uuid

from pydantic import BaseModel

class JobPosition(BaseModel):
    name: str
    confidence: float
    
class JobPost(BaseModel):
    title: str
    url: str
    id: uuid.UUID
    domain_source: str    
    date_added: datetime.datetime
    job_position: str
    snippet: str
    
class JobPostList(BaseModel):
    posts: list[JobPost]
