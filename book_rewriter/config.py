import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Settings:
    nebius_api_key: str
    nebius_base_url: str
    kimi_model: str

    mistral_api_key: str
    mistral_embed_model: str

    index_dir: str

    # Multi-turn rewrite settings
    sambanova_api_key: str = ""
    sambanova_base_url: str = "https://api.sambanova.ai/v1"
    sambanova_model: str = "gpt-oss-120b"
    kimi_instruct_model: str = "moonshotai/Kimi-K2-Instruct"
    kimi_thinking_model: str = "moonshotai/Kimi-K2-Thinking"

    chunk_char_target: int = 1200
    chunk_char_overlap: int = 180
    top_k: int = 10

    # Character tracking settings
    character_ledger_path: str = "metadata/character_ledger.json"
    style_profile_path: str = "metadata/style_profile.json"
    style_sample_size: int = 3

    # Validation settings
    enable_validation: bool = True
    auto_correct_pov: bool = True

    # Pacing settings
    target_word_count_min: int = 2000
    target_word_count_max: int = 3500
    pacing_early_chapters: int = 8
    pacing_middle_chapters: int = 16

    # Context window settings
    previous_chapters_count: int = 3
    future_chapters_count: int = 2

    # Book-aware settings
    book_name: Optional[str] = None
    rewrites_dir: str = "rewrites"
    validation_dir: str = "book_validator"


def load_api_keys_from_env() -> dict:
    """Load API keys from environment variables."""
    return {
        "nebius": os.environ.get("NEBIUS_API_KEY", "").strip(),
        "mistral": os.environ.get("MISTRAL_API_KEY", "").strip(),
        "sambanova": os.environ.get("SAMBANOVA_API_KEY", "").strip(),
    }


def load_api_keys_from_config() -> dict:
    """Load API keys from central config."""
    from .book_manager import load_central_config

    central_config = load_central_config()
    return central_config.get("api_keys", {})


def get_api_key(key_name: str) -> str:
    """Get API key, checking both central config and env vars."""
    config_keys = load_api_keys_from_config()
    env_keys = load_api_keys_from_env()

    return config_keys.get(key_name, env_keys.get(key_name, "")).strip()


def load_settings(book_name: Optional[str] = None) -> Settings:
    """Load settings, optionally for a specific book."""
    # Load from central config
    central_config = load_api_keys_from_config()

    # Load from environment
    env_keys = load_api_keys_from_env()

    nebius_key = central_config.get("nebius", env_keys.get("nebius", ""))
    mistral_key = central_config.get("mistral", env_keys.get("mistral", ""))
    sambanova_key = central_config.get("sambanova", env_keys.get("sambanova", ""))

    settings = Settings(
        nebius_api_key=nebius_key,
        nebius_base_url=os.environ.get(
            "NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/"
        ).strip(),
        kimi_model=os.environ.get("KIMI_MODEL", "moonshotai/Kimi-K2-Instruct").strip(),
        mistral_api_key=mistral_key,
        mistral_embed_model=os.environ.get(
            "MISTRAL_EMBED_MODEL", "mistral-embed"
        ).strip(),
        index_dir=os.environ.get("INDEX_DIR", "local_index").strip(),
        # Multi-turn rewrite settings
        sambanova_api_key=sambanova_key,
        sambanova_base_url=os.environ.get(
            "SAMBANOVA_BASE_URL", "https://api.sambanova.ai/v1"
        ).strip(),
        sambanova_model=os.environ.get("SAMBANOVA_MODEL", "gpt-oss-120b").strip(),
        kimi_instruct_model=os.environ.get(
            "KIMI_INSTRUCT_MODEL", "moonshotai/Kimi-K2-Instruct"
        ).strip(),
        kimi_thinking_model=os.environ.get(
            "KIMI_THINKING_MODEL", "moonshotai/Kimi-K2-Thinking"
        ).strip(),
        # Character tracking settings
        character_ledger_path=os.environ.get(
            "CHARACTER_LEDGER_PATH", "metadata/character_ledger.json"
        ).strip(),
        style_profile_path=os.environ.get(
            "STYLE_PROFILE_PATH", "metadata/style_profile.json"
        ).strip(),
        style_sample_size=int(os.environ.get("STYLE_SAMPLE_SIZE", "3")),
        # Validation settings
        enable_validation=os.environ.get("ENABLE_VALIDATION", "true").lower() == "true",
        auto_correct_pov=os.environ.get("AUTO_CORRECT_POV", "true").lower() == "true",
        # Pacing settings
        target_word_count_min=int(os.environ.get("TARGET_WORD_COUNT_MIN", "2000")),
        target_word_count_max=int(os.environ.get("TARGET_WORD_COUNT_MAX", "3500")),
        pacing_early_chapters=int(os.environ.get("PACING_EARLY_CHAPTERS", "8")),
        pacing_middle_chapters=int(os.environ.get("PACING_MIDDLE_CHAPTERS", "16")),
        # Context window settings
        previous_chapters_count=int(os.environ.get("PREVIOUS_CHAPTERS_COUNT", "3")),
        future_chapters_count=int(os.environ.get("FUTURE_CHAPTERS_COUNT", "2")),
        # Book-aware settings
        book_name=book_name,
    )

    if book_name:
        book_root = os.path.join("books", book_name)
        settings.index_dir = os.path.join(book_root, "index")
        settings.rewrites_dir = os.path.join(book_root, "rewrites")
        settings.validation_dir = os.path.join(book_root, "validation")
        settings.character_ledger_path = os.path.join(
            book_root, "metadata", "character_ledger.json"
        )
        settings.style_profile_path = os.path.join(
            book_root, "metadata", "style_profile.json"
        )

    return settings


def load_settings_legacy(book_name: Optional[str] = None) -> Settings:
    """Legacy load_settings for backwards compatibility."""
    return load_settings(book_name)
