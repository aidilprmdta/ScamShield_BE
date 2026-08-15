"""
Pydantic schemas untuk endpoint /education.
Menerima camelCase (Firestore/seed) maupun snake_case (API).
"""
from enum import Enum
from typing import Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class EducationContentType(str, Enum):
    ARTICLE = "article"
    QUIZ = "quiz"


class QuizQuestion(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    question: str
    options: list[str]
    correct_index: int = Field(
        validation_alias=AliasChoices("correct_index", "correctIndex"),
    )
    explanation: Optional[str] = None


class EducationContentSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str
    title: str
    category: str
    type: EducationContentType
    thumbnail_url: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("thumbnail_url", "thumbnailUrl"),
    )
    published_at: str = Field(
        default="",
        validation_alias=AliasChoices("published_at", "publishedAt"),
    )


class EducationContentDetail(EducationContentSummary):
    body: Optional[str] = Field(default=None, description="Isi artikel (markdown/plain text)")
    quiz_questions: Optional[list[QuizQuestion]] = Field(
        default=None,
        validation_alias=AliasChoices("quiz_questions", "quizQuestions"),
    )


class EducationListResponse(BaseModel):
    success: bool = True
    data: list[EducationContentSummary]


class EducationDetailResponse(BaseModel):
    success: bool = True
    data: EducationContentDetail
