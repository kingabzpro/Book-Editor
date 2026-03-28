"""Settings loaded from environment variables."""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

BOOKS_DIR = "books"
REGISTRY_FILE = "books_registry.json"


@dataclass
class Settings:
    nebius_api_key: str
    nebius_base_url: str
    # Fast model — rewrites, edits  (Kimi 2.5 fast on Nebius)
    kimi_model: str
    # Analysis model — bible, structure  (GLM-5 on Nebius)
    glm_model: str
    # Word count targets per chapter
    target_min: int
    target_max: int
    # How many surrounding chapters to include as context
    prev_chapters: int
    next_chapters: int


def load_settings() -> Settings:
    return Settings(
        nebius_api_key=os.environ.get("NEBIUS_API_KEY", ""),
        nebius_base_url=os.environ.get(
            "NEBIUS_BASE_URL", "https://api.studio.nebius.com/v1/"
        ),
        kimi_model=os.environ.get("KIMI_MODEL", "moonshotai/Kimi-K2-Instruct"),
        glm_model=os.environ.get("GLM_MODEL", "THUDM/GLM-Z1-Rumination-32B"),
        target_min=int(os.environ.get("TARGET_MIN", "2000")),
        target_max=int(os.environ.get("TARGET_MAX", "3500")),
        prev_chapters=int(os.environ.get("PREV_CHAPTERS", "2")),
        next_chapters=int(os.environ.get("NEXT_CHAPTERS", "1")),
    )
