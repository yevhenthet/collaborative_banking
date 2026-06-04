import os
import uvicorn
from pathlib import Path

_env = Path(__file__).parent / ".env"
if _env.exists():
    for _line in _env.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

if __name__ == "__main__":
    host   = os.environ.get("HOST", "127.0.0.1")
    port   = int(os.environ.get("PORT", "8000"))
    reload = os.environ.get("ENV", "production") == "development"
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)
