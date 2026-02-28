"""
Telegram bridge v0: remote commands via Telegram Bot API, guarded by allowlist.

Design goals:
- official Telegram Bot API only
- local state (update offset) persisted
- simple command surface (/help, /status, /route, /chat, /preset)
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import logging
import os
import tempfile
import urllib.error
import urllib.parse
import urllib.request

from .model_control_plane import model_control_plane
from .secret_store import secret_store

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _s(v: Any) -> str:
    return str(v or "").strip()


def _split_csv(v: str) -> List[str]:
    return [x.strip() for x in _s(v).split(",") if x.strip()]


def _state_dir() -> Path:
    for p in [
        Path("storage") / "telegram",
        Path("storage_runtime") / "telegram",
        Path(tempfile.gettempdir()) / "rth_core" / "telegram",
    ]:
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except Exception:
            continue
    p = Path(tempfile.gettempdir()) / "rth_core" / "telegram"
    p.mkdir(parents=True, exist_ok=True)
    return p


class TelegramBridge:
    def __init__(self) -> None:
        self._state_path = _state_dir() / "telegram_bridge_state.json"
        self._state: Dict[str, Any] = {"version": 1, "updated_at": _now(), "offset": 0, "last_poll": None, "last_error": None}
        self._load()

    def _load(self) -> None:
        try:
            if self._state_path.exists():
                payload = json.loads(self._state_path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    self._state.update(payload)
        except Exception as e:
            logger.warning(f"TelegramBridge load failed: {e}")

    def _save(self) -> None:
        try:
            self._state["updated_at"] = _now()
            self._state_path.write_text(json.dumps(self._state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except Exception as e:
            logger.warning(f"TelegramBridge save failed: {e}")

    def _config(self) -> Dict[str, Any]:
        token = secret_store.resolve_env("RTH_TELEGRAM_BOT_TOKEN", "channels/telegram/bot_token")
        allowed = _split_csv(os.getenv("RTH_TELEGRAM_ALLOWED_CHAT_IDS", ""))
        return {
            "token_present": bool(token),
            "token": token,
            "allowed_chat_ids": allowed,
            "webhook_secret": secret_store.resolve_env("RTH_TELEGRAM_WEBHOOK_SECRET", "channels/telegram/webhook_secret"),
        }

    def status(self) -> Dict[str, Any]:
        cfg = self._config()
        return {
            "status": "ok",
            "module": "telegram_bridge",
            "configured": bool(cfg["token_present"]),
            "allowed_chat_ids_count": len(cfg["allowed_chat_ids"]),
            "state": {
                "offset": int(self._state.get("offset") or 0),
                "last_poll": self._state.get("last_poll"),
                "last_error": self._state.get("last_error"),
                "state_path": str(self._state_path),
            },
        }

    def _api_url(self, method: str) -> str:
        token = self._config()["token"]
        return f"https://api.telegram.org/bot{token}/{method}"

    def _http_json(self, url: str, *, method: str = "GET", payload: Optional[Dict[str, Any]] = None, timeout_sec: float = 20.0) -> Dict[str, Any]:
        headers = {"Accept": "application/json", "User-Agent": "RTH-Core/0.1 (+TelegramBridge)"}
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, headers=headers, data=data, method=method)
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            body = json.loads(raw) if raw.strip() else {}
            return {"ok": True, "status_code": int(getattr(resp, "status", 200)), "body": body, "raw_preview": raw[:800]}

    def get_me(self, timeout_sec: float = 10.0) -> Dict[str, Any]:
        cfg = self._config()
        if not cfg["token_present"]:
            return {"status": "missing_config", "detail": "RTH_TELEGRAM_BOT_TOKEN missing"}
        try:
            res = self._http_json(self._api_url("getMe"), timeout_sec=timeout_sec)
            return {"status": "ok", "telegram": res.get("body")}
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", errors="replace")[:1200]
            except Exception:
                pass
            return {"status": "error", "error": str(e), "status_code": getattr(e, "code", None), "detail": detail}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def poll_once(self, limit: int = 10, timeout_sec: float = 20.0, auto_reply: bool = True) -> Dict[str, Any]:
        cfg = self._config()
        if not cfg["token_present"]:
            return {"status": "missing_config", "detail": "RTH_TELEGRAM_BOT_TOKEN missing"}
        offset = int(self._state.get("offset") or 0)
        payload = {"timeout": 0, "limit": max(1, min(int(limit), 50))}
        if offset > 0:
            payload["offset"] = offset + 1
        try:
            res = self._http_json(self._api_url("getUpdates"), method="POST", payload=payload, timeout_sec=timeout_sec)
            body = res.get("body") if isinstance(res.get("body"), dict) else {}
            updates = body.get("result") if isinstance(body, dict) else []
            processed = []
            max_update = offset
            for u in updates or []:
                if not isinstance(u, dict):
                    continue
                uid = int(u.get("update_id") or 0)
                max_update = max(max_update, uid)
                processed.append(self.handle_update(u, auto_reply=auto_reply))
            self._state["offset"] = max_update
            self._state["last_poll"] = _now()
            self._state["last_error"] = None
            self._save()
            return {"status": "ok", "count": len(processed), "processed": processed}
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", errors="replace")[:1200]
            except Exception:
                pass
            self._state["last_error"] = f"{e}"
            self._save()
            return {"status": "error", "error": str(e), "status_code": getattr(e, "code", None), "detail": detail}
        except Exception as e:
            self._state["last_error"] = str(e)
            self._save()
            return {"status": "error", "error": str(e)}

    def send_text(self, chat_id: str, text: str, timeout_sec: float = 20.0) -> Dict[str, Any]:
        cfg = self._config()
        if not cfg["token_present"]:
            return {"status": "missing_config", "detail": "RTH_TELEGRAM_BOT_TOKEN missing"}
        try:
            payload = {"chat_id": chat_id, "text": text[:4000]}
            res = self._http_json(self._api_url("sendMessage"), method="POST", payload=payload, timeout_sec=timeout_sec)
            return {"status": "ok", "telegram": res.get("body")}
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", errors="replace")[:1200]
            except Exception:
                pass
            return {"status": "error", "error": str(e), "status_code": getattr(e, "code", None), "detail": detail}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def handle_webhook_update(self, update: Dict[str, Any], auto_reply: bool = True) -> Dict[str, Any]:
        return self.handle_update(update, auto_reply=auto_reply)

    def handle_update(self, update: Dict[str, Any], auto_reply: bool = True, send_mode: str = "live") -> Dict[str, Any]:
        msg = update.get("message") if isinstance(update.get("message"), dict) else update.get("edited_message")
        if not isinstance(msg, dict):
            return {"status": "ignored", "reason": "no_message", "update_id": update.get("update_id")}
        chat = msg.get("chat") if isinstance(msg.get("chat"), dict) else {}
        chat_id = str(chat.get("id") or "").strip()
        text = _s(msg.get("text"))
        from_user = msg.get("from") if isinstance(msg.get("from"), dict) else {}
        cfg = self._config()
        allowed = set(cfg["allowed_chat_ids"])
        if allowed and chat_id not in allowed:
            return {"status": "ignored", "reason": "chat_not_allowed", "chat_id": chat_id, "text": text[:120]}
        out = {"status": "ok", "chat_id": chat_id, "from": from_user.get("username") or from_user.get("id"), "text": text[:500], "reply": None}
        if not text:
            return out
        reply = self._dispatch_text_command(text)
        out["reply"] = reply
        if auto_reply and chat_id and isinstance(reply, dict):
            reply_text = _s(reply.get("text"))
            if reply_text:
                out["send_result"] = self._send_text_by_mode(chat_id, reply_text, mode=send_mode)
        return out

    def replay_text(self, text: str, chat_id: str = "999000111", username: str = "owner_test", auto_reply: bool = True) -> Dict[str, Any]:
        update = {
            "update_id": int(datetime.now().timestamp()),
            "message": {
                "message_id": 1,
                "date": int(datetime.now().timestamp()),
                "chat": {"id": chat_id, "type": "private"},
                "from": {"id": 1, "username": username, "is_bot": False},
                "text": text,
            },
        }
        result = self.handle_update(update, auto_reply=auto_reply, send_mode="replay")
        self._state["last_poll"] = _now()
        self._state["last_error"] = None
        self._save()
        return {"status": "ok", "mode": "replay", "input": {"chat_id": chat_id, "text": text}, "result": result}

    def _send_text_by_mode(self, chat_id: str, text: str, mode: str = "live") -> Dict[str, Any]:
        if _s(mode).lower() == "replay":
            return {
                "status": "ok",
                "mode": "replay",
                "chat_id": chat_id,
                "text_preview": _s(text)[:500],
                "sent_at": _now(),
            }
        return self.send_text(chat_id, text)

    def _dispatch_text_command(self, text: str) -> Dict[str, Any]:
        raw = _s(text)
        low = raw.lower()
        if low.startswith("/help") or low == "help":
            return {"text": "Comandi: /status, /models, /route <msg>, /chat <msg>, /preset <id>", "type": "help"}
        if low.startswith("/status"):
            ms = model_control_plane.status()
            return {"text": f"RTH ok | providers={ms.get('providers_total')} enabled={ms.get('providers_enabled')} catalog={ms.get('catalog_models')}", "type": "status"}
        if low.startswith("/models"):
            cat = model_control_plane.get_catalog()
            sample = [x.get("ref") for x in (cat.get("items") or [])[:8] if isinstance(x, dict)]
            return {"text": f"Catalogo modelli ({cat.get('count')}): " + ", ".join(sample), "type": "models"}
        if low.startswith("/preset "):
            preset_id = raw.split(" ", 1)[1].strip()
            res = model_control_plane.apply_preset(preset_id, reason="Telegram preset apply", confirm_owner=True, decided_by="owner")
            return {"text": f"preset {preset_id}: {res.get('status')}", "type": "preset", "data": res}
        if low.startswith("/route "):
            prompt = raw.split(" ", 1)[1].strip()
            res = model_control_plane.route_explain({"message": prompt, "task_class": "chat_general", "privacy_mode": "allow_cloud"})
            sel = (res.get("selected") or {}).get("ref")
            return {"text": f"route: {res.get('status')} | selected={sel}", "type": "route", "data": res}
        if low.startswith("/chat "):
            prompt = raw.split(" ", 1)[1].strip()
            res = model_control_plane.chat_execute({
                "message": prompt,
                "task_class": "chat_general",
                "privacy_mode": "allow_cloud",
                "confirm_owner": True,
                "decided_by": "owner",
                "reason": "Telegram remote chat",
                "timeout_sec": 60,
                "max_tokens": 500,
                "temperature": 0.2,
            })
            txt = _s(res.get("assistant_message") or res.get("assistant_preview") or res.get("status"))
            return {"text": txt[:3500], "type": "chat", "data": {"status": res.get("status"), "selected": (res.get("selected_model") or {}).get("ref")}}
        return {"text": "Comando non riconosciuto. Usa /help", "type": "unknown"}


telegram_bridge = TelegramBridge()
