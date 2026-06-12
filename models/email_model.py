from pydantic import BaseModel
from typing import Optional


class EmailRequest(BaseModel):
    company_name: Optional[str] = ""
    website:      Optional[str] = ""
    email:        Optional[str] = ""
    country:      Optional[str] = ""
    linkedin:     Optional[str] = ""
    score:        Optional[int] = 0
    tag:          Optional[str] = "unscored"   # hot / warm / cold
    service:      Optional[str] = ""           # what your company offers


class EmailResponse(BaseModel):
    success:      bool
    subject:      str
    body:         str
    generated_by: str   # "claude-ai" | "openai" | "template"