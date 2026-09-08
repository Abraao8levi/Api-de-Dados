import json
import os
from datetime import datetime, timezone
from pathlib import Path

CACHE_DIR = Path(__file__).parent / ".cache"
TTL_HORAS = 24


def _cache_path(key: str) -> Path:
    safe = key.replace("/", "__")
    return CACHE_DIR / f"{safe}.json"


def _is_expired(timestamp_iso: str) -> bool:
    saved_at = datetime.fromisoformat(timestamp_iso)
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
    with open(_cache_path(key), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, default=str)


def carregar(key: str) -> dict | None:
    path = _cache_path(key)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if _is_expired(payload["saved_at"]):
        path.unlink()
        return None
    return payload["dados"]


def invalidar(key: str) -> None:
    path = _cache_path(key)
    if path.exists():
        path.unlink()


def info(key: str) -> dict | None:
    path = _cache_path(key)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    saved_at = datetime.fromisoformat(payload["saved_at"])
    if saved_at.tzinfo is None:
        saved_at = saved_at.replace(tzinfo=timezone.utc)
    elapsed = (datetime.now(timezone.utc) - saved_at).total_seconds() / 3600
    expira_em = max(0.0, TTL_HORAS - elapsed)
    return {
        "saved_at": payload["saved_at"],
        "expira_em_horas": round(expira_em, 2),
        "expirado": _is_expired(payload["saved_at"]),
    }
