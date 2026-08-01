"""
Pydantic schemas untuk endpoint /education.
"""
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EducationContentType(str, Enum):
    ARTICLE = "article"
    QUIZ = "quiz"


class QuizQuestion(BaseModel):
    question: str
    options: list[str]
    correct_index: int
    explanation: Optional[str] = None


class EducationContentSummary(BaseModel):
    id: str
    title: str
    category: str
    type: EducationContentType
    thumbnail_url: Optional[str] = None
    published_at: str


class EducationContentDetail(EducationContentSummary):
    body: Optional[str] = Field(default=None, description="Isi artikel (markdown/plain text)")
    quiz_questions: Optional[list[QuizQuestion]] = None


class EducationListResponse(BaseModel):
    success: bool = True
    data: list[EducationContentSummary]


class EducationDetailResponse(BaseModel):
    success: bool = True
    data: EducationContentDetail
