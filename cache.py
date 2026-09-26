import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

CACHE_DIR = Path(__file__).parent / ".cache"
TTL_HORAS = 24


def _cache_path(key: str) -> Path:
    safe = key.replace("/", "__").replace("\\", "__").replace("..", "_").replace(":", "__")
    return CACHE_DIR / f"{safe}.json"


def _is_expired(timestamp_iso: str) -> bool:
    try:
        saved_at = datetime.fromisoformat(timestamp_iso)
    except (ValueError, TypeError):
        return True
    if saved_at.tzinfo is None:
        saved_at = saved_at.replace(tzinfo=timezone.utc)
    elapsed = (datetime.now(timezone.utc) - saved_at).total_seconds() / 3600
    return elapsed > TTL_HORAS


def salvar(key: str, dados: dict) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    payload = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "dados": dados,
    }
    target_path = _cache_path(key)
    temp_fd, temp_path = tempfile.mkstemp(dir=CACHE_DIR, suffix=".tmp")
    try:
        with open(temp_fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, default=str)
        os.replace(temp_path, target_path)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


def carregar(key: str) -> dict | None:
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except (json.JSONDecodeError, OSError):
        path.unlink(missing_ok=True)
        return None

    saved_at = payload.get("saved_at", "")
    if not saved_at or _is_expired(saved_at):
        path.unlink(missing_ok=True)
        return None
    return payload.get("dados")


def invalidar(key: str) -> None:
    _cache_path(key).unlink(missing_ok=True)


def info(key: str) -> dict | None:
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    saved_at_raw = payload.get("saved_at")
    if not saved_at_raw:
        return None

    try:
        saved_at = datetime.fromisoformat(saved_at_raw)
    except (ValueError, TypeError):
        return None

    if saved_at.tzinfo is None:
        saved_at = saved_at.replace(tzinfo=timezone.utc)
    elapsed = (datetime.now(timezone.utc) - saved_at).total_seconds() / 3600
    expira_em = max(0.0, TTL_HORAS - elapsed)
    return {
        "saved_at": saved_at_raw,
        "expira_em_horas": round(expira_em, 2),
        "expirado": _is_expired(saved_at_raw),
    }
