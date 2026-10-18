import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from the project root
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

class AppConfig:
    """Central configuration management for the YouTube Shorts Pipeline."""

    # Project Directories
    BASE_DIR: Path = ROOT_DIR
    OUTPUT_DIR: Path = ROOT_DIR / os.getenv("OUTPUT_DIR", "outputs")
    TEMP_DIR: Path = ROOT_DIR / "temp"

    # LLM Configuration
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip()

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "").strip()
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o").strip()

    DEFAULT_LLM_PROVIDER: str = os.getenv("DEFAULT_LLM_PROVIDER", "gemini").strip().lower()

    # Voice / Audio Configuration
    TTS_PROVIDER: str = os.getenv("TTS_PROVIDER", "edge-tts").strip().lower()
    EDGE_TTS_VOICE: str = os.getenv("EDGE_TTS_VOICE", "en-US-ChristopherNeural").strip()
    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "").strip()
    ELEVENLABS_VOICE_ID: str = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM").strip()

    # Media & Stock Footage Configuration
    PEXELS_API_KEY: str = os.getenv("PEXELS_API_KEY", "").strip()
    PIXABAY_API_KEY: str = os.getenv("PIXABAY_API_KEY", "").strip()
    BACKGROUNDS_DIR: Path = ROOT_DIR / "assets" / "backgrounds"

    # YouTube Publishing Configuration
    YOUTUBE_CLIENT_SECRETS_FILE: Path = ROOT_DIR / os.getenv("YOUTUBE_CLIENT_SECRETS_FILE", "client_secrets.json")
    YOUTUBE_TOKEN_FILE: Path = ROOT_DIR / os.getenv("YOUTUBE_TOKEN_FILE", "token.json")

    @classmethod
    def get_gemini_key(cls) -> str:
        return (os.getenv("GEMINI_API_KEY") or cls.GEMINI_API_KEY or "").strip()

    @classmethod
    def get_gemini_model(cls) -> str:
        return (os.getenv("GEMINI_MODEL") or cls.GEMINI_MODEL or "gemini-3.1-flash-lite").strip()

    @classmethod
    def get_openai_key(cls) -> str:
        return (os.getenv("OPENAI_API_KEY") or cls.OPENAI_API_KEY or "").strip()

    @classmethod
    def get_pixabay_key(cls) -> str:
        return (os.getenv("PIXABAY_API_KEY") or cls.PIXABAY_API_KEY or "").strip()

    @classmethod
    def get_pexels_key(cls) -> str:
        return (os.getenv("PEXELS_API_KEY") or cls.PEXELS_API_KEY or "").strip()

    @classmethod
    def reload(cls) -> None:
        """Reload configuration from .env file."""
        load_dotenv(ROOT_DIR / ".env", override=True)
        cls.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
        cls.GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite").strip()
        cls.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
        cls.OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o").strip()
        cls.DEFAULT_LLM_PROVIDER = os.getenv("DEFAULT_LLM_PROVIDER", "gemini").strip().lower()
        cls.PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "").strip()
        cls.PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "").strip()
        cls.TTS_PROVIDER = os.getenv("TTS_PROVIDER", "edge-tts").strip().lower()
        cls.EDGE_TTS_VOICE = os.getenv("EDGE_TTS_VOICE", "en-US-ChristopherNeural").strip()
        cls.ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()

    @classmethod
    def update_env_key(cls, key: str, value: str) -> None:
        """Update a key in the .env file and reload config."""
        env_path = ROOT_DIR / ".env"
        lines = []
        key_found = False

        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith(f"{key}=") or line.startswith(f"{key} ="):
                    lines.append(f"{key}={value}")
                    key_found = True
                else:
                    lines.append(line)

        if not key_found:
            lines.append(f"{key}={value}")

        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        cls.reload()

    @classmethod
    def initialize_dirs(cls) -> None:
        """Ensure necessary output and temporary folders exist."""
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.TEMP_DIR.mkdir(parents=True, exist_ok=True)


# Automatically ensure working directories are available
AppConfig.initialize_dirs()
