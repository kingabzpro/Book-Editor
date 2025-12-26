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

    chunk_char_target: int = 1200
    chunk_char_overlap: int = 180
    top_k: int = 10

def load_settings() -> Settings:
    return Settings(
        nebius_api_key=os.environ.get("NEBIUS_API_KEY", "").strip(),
        nebius_base_url=os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/").strip(),
        kimi_model=os.environ.get("KIMI_MODEL", "moonshotai/Kimi-K2-Instruct").strip(),

        mistral_api_key=os.environ.get("MISTRAL_API_KEY", "").strip(),
        mistral_embed_model=os.environ.get("MISTRAL_EMBED_MODEL", "mistral-embed").strip(),

        index_dir=os.environ.get("INDEX_DIR", "local_index").strip(),
    )
