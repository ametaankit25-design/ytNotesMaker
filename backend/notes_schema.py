from pydantic import BaseModel, Field
from typing import List, Optional


class Flashcard(BaseModel):
    """A single Q&A flashcard for studying."""
    question: str = Field(description="A study question based on the video content")
    answer: str = Field(description="The concise answer to the question")


class NotesOutput(BaseModel):
    """
    Structured notes extracted from a YouTube video transcript.
    This is the schema the LLM must conform to via with_structured_output().
    """
    title: str = Field(
        description="A descriptive title for the video based on its content"
    )
    summary: str = Field(
        description="A thorough 2-3 paragraph summary of the video's main ideas"
    )
    key_concepts: List[str] = Field(
        description="5 to 10 key concepts, terms, or topics explained in the video"
    )
    bullet_points: List[str] = Field(
        description="15 to 20 detailed bullet-point notes capturing the most important information"
    )
    flashcards: List[Flashcard] = Field(
        description="Exactly 10 Q&A flashcard pairs to help study the content"
    )
    important_quotes: Optional[List[str]] = Field(
        default=[],
        description="Up to 5 notable statements or quotes from the video (if any)"
    )
