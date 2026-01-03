from dataclasses import dataclass
import os

@dataclass(frozen=True)
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

def load_settings() -> Settings:
    return Settings(
        nebius_api_key=os.environ.get("NEBIUS_API_KEY", "").strip(),
        nebius_base_url=os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/").strip(),
        kimi_model=os.environ.get("KIMI_MODEL", "moonshotai/Kimi-K2-Instruct").strip(),

        mistral_api_key=os.environ.get("MISTRAL_API_KEY", "").strip(),
        mistral_embed_model=os.environ.get("MISTRAL_EMBED_MODEL", "mistral-embed").strip(),

        index_dir=os.environ.get("INDEX_DIR", "local_index").strip(),

        # Multi-turn rewrite settings
        sambanova_api_key=os.environ.get("SAMBANOVA_API_KEY", "").strip(),
        sambanova_base_url=os.environ.get("SAMBANOVA_BASE_URL", "https://api.sambanova.ai/v1").strip(),
        sambanova_model=os.environ.get("SAMBANOVA_MODEL", "gpt-oss-120b").strip(),
        kimi_instruct_model=os.environ.get("KIMI_INSTRUCT_MODEL", "moonshotai/Kimi-K2-Instruct").strip(),
        kimi_thinking_model=os.environ.get("KIMI_THINKING_MODEL", "moonshotai/Kimi-K2-Thinking").strip(),

        # Character tracking settings
        character_ledger_path=os.environ.get("CHARACTER_LEDGER_PATH", "metadata/character_ledger.json").strip(),
        style_profile_path=os.environ.get("STYLE_PROFILE_PATH", "metadata/style_profile.json").strip(),
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
    )
