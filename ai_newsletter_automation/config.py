import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    tavily_api_key: str
    groq_api_key: str
    outlook_subject_prefix: str = "AI This Week | Key AI Developments You Should Know"
    run_days: int = 7
    max_per_stream: Optional[int] = None
    project_root: Path = Path(__file__).resolve().parent.parent

    @property
    def today_str(self) -> str:
        return date.today().isoformat()


def get_settings() -> Settings:
    tavily = os.getenv("TAVILY_API_KEY", "")
    groq = os.getenv("GROQ_API_KEY", "")
    if not tavily:
        raise RuntimeError("Missing TAVILY_API_KEY in environment or .env")
    if not groq:
        raise RuntimeError("Missing GROQ_API_KEY in environment or .env")

    return Settings(
        tavily_api_key=tavily,
        groq_api_key=groq,
        outlook_subject_prefix=os.getenv(
            "OUTLOOK_SUBJECT_PREFIX",
            "AI This Week | Key AI Developments You Should Know",
        ),
        run_days=int(os.getenv("RUN_DAYS", "7")),
        max_per_stream=int(os.getenv("MAX_PER_STREAM") or "0") or None,
    )
