import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
import re


BOOKS_DIR = "books"
REGISTRY_FILE = "books_registry.json"
CENTRAL_CONFIG_FILE = "central_config.json"


def sanitize_name(name: str) -> str:
    """Sanitize filename by removing invalid characters and converting to lowercase."""
    # Remove invalid characters
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    # Replace spaces with underscores and convert to lowercase
    name = name.replace(" ", "_").lower()
    # Limit length
    return name[:50]


def create_book_name_from_docx(docx_path: str) -> str:
    """Generate book name from DOCX filename."""
    filename = Path(docx_path).stem
    book_name = sanitize_name(filename)
    return book_name


def ensure_books_dir():
    """Ensure books directory exists."""
    Path(BOOKS_DIR).mkdir(exist_ok=True)


def load_registry() -> Dict:
    """Load books registry."""
    if not os.path.exists(REGISTRY_FILE):
        return {"active_book": None, "books": {}}
    with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_registry(registry: Dict):
    """Save books registry."""
    with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)


def get_book_path(book_name: str) -> Path:
    """Get full path to book directory."""
    return Path(BOOKS_DIR) / book_name


def get_book_source_path(book_name: str) -> Path:
    """Get path to book's source directory."""
    return get_book_path(book_name) / "source"


def get_book_metadata_path(book_name: str) -> Path:
    """Get path to book's metadata directory."""
    return get_book_path(book_name) / "metadata"


def get_book_rewrites_path(book_name: str) -> Path:
    """Get path to book's rewrites directory."""
    return get_book_path(book_name) / "rewrites"


def get_book_validation_path(book_name: str) -> Path:
    """Get path to book's validation directory."""
    return get_book_path(book_name) / "validation"


def get_book_index_path(book_name: str) -> Path:
    """Get path to book's index directory."""
    return get_book_path(book_name) / "index"


def get_book_config_path(book_name: str) -> Path:
    """Get path to book's config file."""
    return get_book_path(book_name) / "config.json"


def create_book_structure(book_name: str, docx_path: str) -> Dict:
    """Create book folder structure and initialize configuration."""
    book_path = get_book_path(book_name)

    if book_path.exists():
        raise ValueError(f"Book '{book_name}' already exists at {book_path}")

    ensure_books_dir()

    source_path = get_book_source_path(book_name)
    metadata_path = get_book_metadata_path(book_name)
    rewrites_path = get_book_rewrites_path(book_name)
    validation_path = get_book_validation_path(book_name)
    index_path = get_book_index_path(book_name)

    for path in [
        source_path,
        metadata_path,
        rewrites_path,
        validation_path,
        index_path,
    ]:
        path.mkdir(parents=True, exist_ok=True)

    source_file = source_path / Path(docx_path).name
    shutil.copy2(docx_path, source_file)

    book_info = {
        "name": Path(docx_path).stem,
        "created": datetime.now().isoformat(),
        "source_file": Path(docx_path).name,
        "total_chapters": 0,
        "last_modified": datetime.now().isoformat(),
    }

    config = {
        "book_name": book_name,
        "display_name": Path(docx_path).stem,
        "created": datetime.now().isoformat(),
        "settings": {},
    }

    with open(get_book_config_path(book_name), "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    registry = load_registry()
    registry["books"][book_name] = book_info
    if not registry["active_book"]:
        registry["active_book"] = book_name
    save_registry(registry)

    return book_info


def list_books() -> List[Dict]:
    """List all registered books."""
    registry = load_registry()
    books = []
    for book_name, book_info in registry["books"].items():
        books.append(
            {
                "name": book_name,
                "display_name": book_info.get("name", book_name),
                "created": book_info.get("created", "unknown"),
                "total_chapters": book_info.get("total_chapters", 0),
                "last_modified": book_info.get("last_modified", "unknown"),
                "is_active": book_name == registry["active_book"],
            }
        )
    return books


def get_active_book() -> Optional[str]:
    """Get the currently active book name."""
    registry = load_registry()
    return registry.get("active_book")


def set_active_book(book_name: str):
    """Set the active book."""
    registry = load_registry()
    if book_name not in registry["books"]:
        raise ValueError(f"Book '{book_name}' not found in registry")
    registry["active_book"] = book_name
    save_registry(registry)


def delete_book(book_name: str) -> bool:
    """Delete a book and all its data."""
    book_path = get_book_path(book_name)

    if not book_path.exists():
        raise ValueError(f"Book '{book_name}' not found")

    shutil.rmtree(book_path)

    registry = load_registry()
    if book_name in registry["books"]:
        del registry["books"][book_name]
        if registry["active_book"] == book_name:
            registry["active_book"] = (
                list(registry["books"].keys())[0] if registry["books"] else None
            )
        save_registry(registry)

    return True


def update_book_info(book_name: str, updates: Dict):
    """Update book information in registry."""
    registry = load_registry()
    if book_name not in registry["books"]:
        raise ValueError(f"Book '{book_name}' not found in registry")

    registry["books"][book_name].update(updates)
    registry["books"][book_name]["last_modified"] = datetime.now().isoformat()
    save_registry(registry)


def validate_book_structure(book_name: str) -> Dict:
    """Validate book folder structure and report issues."""
    book_path = get_book_path(book_name)

    if not book_path.exists():
        return {"valid": False, "issues": [f"Book directory not found: {book_path}"]}

    issues = []

    required_dirs = {
        "source": get_book_source_path(book_name),
        "metadata": get_book_metadata_path(book_name),
        "rewrites": get_book_rewrites_path(book_name),
        "validation": get_book_validation_path(book_name),
        "index": get_book_index_path(book_name),
    }

    for dir_name, dir_path in required_dirs.items():
        if not dir_path.exists():
            issues.append(f"Missing directory: {dir_name}/")

    config_path = get_book_config_path(book_name)
    if not config_path.exists():
        issues.append(f"Missing file: config.json")

    return {"valid": len(issues) == 0, "issues": issues}


def load_central_config() -> Dict:
    """Load central configuration."""
    if not os.path.exists(CENTRAL_CONFIG_FILE):
        return {}
    with open(CENTRAL_CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_central_config(config: Dict):
    """Save central configuration."""
    with open(CENTRAL_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def load_book_config(book_name: str) -> Dict:
    """Load book-specific configuration."""
    config_path = get_book_config_path(book_name)
    if not config_path.exists():
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_book_config(book_name: str, config: Dict):
    """Save book-specific configuration."""
    config_path = get_book_config_path(book_name)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def get_effective_config(book_name: str = None) -> Dict:
    """Get effective configuration by merging central and book-specific configs."""
    central_config = load_central_config()

    if book_name:
        book_config = load_book_config(book_name)
        settings = central_config.get("default_settings", {}).copy()
        settings.update(book_config.get("settings", {}))
    else:
        settings = central_config.get("default_settings", {})

    return {"api_keys": central_config.get("api_keys", {}), "settings": settings}
