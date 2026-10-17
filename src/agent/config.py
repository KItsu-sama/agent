"""Environment-backed application settings."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class Settings:
    api_key: str
    model: str
    base_url: str | None
    data_dir: Path

    @classmethod
    def from_environment(cls) -> "Settings":
        load_dotenv()
        api_key = os.getenv("LLM_API_KEY", "").strip()
        if not api_key:
            raise ValueError("Set LLM_API_KEY in the environment or .env file.")

        base_url = os.getenv("LLM_BASE_URL", "").strip() or None
        configured_data_dir = os.getenv("CODE_AGENT_DATA_DIR", "").strip() or "data"
        data_dir = Path(configured_data_dir).expanduser()
        return cls(
            api_key=api_key,
            model=os.getenv("LLM_MODEL", "").strip() or "gpt-5.5",
            base_url=base_url,
            data_dir=data_dir.resolve(),
        )
