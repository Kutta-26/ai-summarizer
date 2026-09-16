import os
from pathlib import Path
from dotenv import load_dotenv

# Search for .env in current directory, backend folder, and project root
_base_dir = Path(__file__).resolve().parent.parent.parent
_root_dir = _base_dir.parent

load_dotenv()
load_dotenv(_base_dir / ".env")
load_dotenv(_root_dir / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 10 * 1024 * 1024))  # 10 MB default
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "60.0"))  # 60 seconds default
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small")

# Standardized uploads folder (inside backend directory)
UPLOAD_DIR = _base_dir / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Configurable CORS origins for production and local development
_raw_cors = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000"
)
CORS_ORIGINS = [origin.strip() for origin in _raw_cors.split(",") if origin.strip()]
