"""
Pydantic models for AI Newsletter Curation System
"""

from typing import List, Literal
from pydantic import BaseModel, Field


class SelectedArticle(BaseModel):
    """선택된 기사 정보"""
    source: Literal["alphaxiv", "hf_blog", "venturebeat", "ai_times"]
    index: int = Field(..., description="해당 소스 내 기사 인덱스 (0-based)")
    title: str
    reason_for_selection: str = Field(..., description="선정 이유 (2-3문장, 영어)")


class CurationResult(BaseModel):
    """카테고리별 큐레이션 결과"""
    category: Literal["academic", "technews"]
    selected_articles: List[SelectedArticle] = Field(
        ...,
        min_length=1,
        max_length=3,
        description="선정된 기사 목록 (1~3개)"
    )


class ArticleSummary(BaseModel):
    """뉴스레터에 포함될 기사 요약"""
    title: str = Field(..., description="기사 제목")
    summary_points: List[str] = Field(
        ...,
        description="기사 요약 개조식 서술 (3-5개 bullet points, 각 포인트는 1-2문장, 전문적/학술적 톤)"
    )
    url: str = Field(..., description="원문 URL")
    source: str = Field(..., description="출처 (alphaxiv, hf_blog, venturebeat, ai_times)")


class Newsletter(BaseModel):
    """AI 뉴스레터 전체 구조"""
    greeting: str = Field(..., description="인사말 (1-2문장)")
    academic_section_intro: str = Field(..., description="Academic 섹션 소개 (1-2문장)")
    academic_articles: List[ArticleSummary] = Field(..., description="Academic 기사 목록")
    technews_section_intro: str = Field(..., description="Tech News 섹션 소개 (1-2문장)")
    technews_articles: List[ArticleSummary] = Field(..., description="Tech News 기사 목록")
    closing: str = Field(..., description="마무리 인사 (1-2문장)")
