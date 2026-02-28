"""
WhatsApp bridge v0 (official providers only): Meta Cloud API or Twilio.

Focus:
- configuration/status
- Meta webhook verification + payload parsing
- send text helper (Meta/Twilio)
- command parsing scaffold (/status, /route, /chat)
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
import base64
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


def _csv(v: str) -> List[str]:
    return [x.strip() for x in _s(v).split(",") if x.strip()]


def _state_dir() -> Path:
    for p in [Path("storage") / "whatsapp", Path("storage_runtime") / "whatsapp", Path(tempfile.gettempdir()) / "rth_core" / "whatsapp"]:
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except Exception:
            continue
    p = Path(tempfile.gettempdir()) / "rth_core" / "whatsapp"
    p.mkdir(parents=True, exist_ok=True)
    return p


class WhatsAppBridge:
    def __init__(self) -> None:
        self._state_path = _state_dir() / "whatsapp_bridge_state.json"
        self._state: Dict[str, Any] = {"version": 1, "updated_at": _now(), "last_webhook": None, "last_error": None}
        self._load()

    def _load(self) -> None:
        try:
            if self._state_path.exists():
                payload = json.loads(self._state_path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    self._state.update(payload)
        except Exception as e:
            logger.warning(f"WhatsAppBridge load failed: {e}")

    def _save(self) -> None:
        try:
            self._state["updated_at"] = _now()
            self._state_path.write_text(json.dumps(self._state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except Exception as e:
            logger.warning(f"WhatsAppBridge save failed: {e}")

    def _cfg(self) -> Dict[str, Any]:
        provider = _s(os.getenv("RTH_WHATSAPP_PROVIDER")).lower() or "meta_cloud"
        return {
            "provider": provider,
            "meta": {
                "access_token": secret_store.resolve_env("RTH_WHATSAPP_META_ACCESS_TOKEN", "channels/whatsapp/meta/access_token"),
                "phone_number_id": _s(os.getenv("RTH_WHATSAPP_META_PHONE_NUMBER_ID")),
                "verify_token": secret_store.resolve_env("RTH_WHATSAPP_META_VERIFY_TOKEN", "channels/whatsapp/meta/verify_token"),
                "allowed_numbers": _csv(os.getenv("RTH_WHATSAPP_ALLOWED_NUMBERS", "")),
            },
            "twilio": {
                "account_sid": secret_store.resolve_env("RTH_TWILIO_ACCOUNT_SID", "channels/whatsapp/twilio/account_sid"),
                "auth_token": secret_store.resolve_env("RTH_TWILIO_AUTH_TOKEN", "channels/whatsapp/twilio/auth_token"),
                "from_number": _s(os.getenv("RTH_TWILIO_WHATSAPP_FROM")),
                "allowed_numbers": _csv(os.getenv("RTH_TWILIO_WHATSAPP_ALLOWED_NUMBERS", "")),
            },
        }

    def status(self) -> Dict[str, Any]:
        cfg = self._cfg()
        meta = cfg["meta"]
        tw = cfg["twilio"]
        return {
            "status": "ok",
            "module": "whatsapp_bridge",
            "provider": cfg["provider"],
            "meta_configured": bool(meta["access_token"] and meta["phone_number_id"]),
            "twilio_configured": bool(tw["account_sid"] and tw["auth_token"] and tw["from_number"]),
            "allowed_numbers_count": len(meta["allowed_numbers"] or tw["allowed_numbers"]),
            "state": {
                "last_webhook": self._state.get("last_webhook"),
                "last_error": self._state.get("last_error"),
                "state_path": str(self._state_path),
            },
        }

    def meta_verify_webhook(self, mode: str, verify_token: str, challenge: str) -> Dict[str, Any]:
        cfg = self._cfg()["meta"]
        expected = _s(cfg.get("verify_token"))
        ok = (_s(mode) == "subscribe") and expected and (_s(verify_token) == expected)
        return {"status": "ok" if ok else "denied", "challenge": challenge if ok else None}

    def handle_meta_webhook(self, payload: Dict[str, Any], auto_reply: bool = False, send_mode: str = "live") -> Dict[str, Any]:
        parsed = self._parse_meta_messages(payload)
        self._state["last_webhook"] = _now()
        self._state["last_error"] = None
        self._save()
        out_rows = []
        for row in parsed:
            result = {"inbound": row, "action": "parsed"}
            txt = _s(row.get("text"))
            if auto_reply and txt:
                reply = self._dispatch_text_command(txt)
                result["reply"] = reply
                if row.get("from") and _s(reply.get("text")):
                    result["send_result"] = self._send_text_by_mode(_s(row.get("from")), _s(reply.get("text")), mode=send_mode)
            out_rows.append(result)
        return {"status": "ok", "count": len(out_rows), "events": out_rows}

    def replay_text(self, text: str, from_number: str = "15550001111", auto_reply: bool = True) -> Dict[str, Any]:
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "from": from_number,
                                        "id": f"wamid.replay.{int(datetime.now().timestamp())}",
                                        "timestamp": str(int(datetime.now().timestamp())),
                                        "type": "text",
                                        "text": {"body": text},
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }
        out = self.handle_meta_webhook(payload, auto_reply=auto_reply, send_mode="replay")
        return {"status": "ok", "mode": "replay", "provider": "meta_cloud", "payload": payload, "result": out}

    def _parse_meta_messages(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        entries = payload.get("entry") if isinstance(payload.get("entry"), list) else []
        for entry in entries:
            changes = entry.get("changes") if isinstance(entry, dict) and isinstance(entry.get("changes"), list) else []
            for ch in changes:
                value = ch.get("value") if isinstance(ch, dict) and isinstance(ch.get("value"), dict) else {}
                msgs = value.get("messages") if isinstance(value.get("messages"), list) else []
                for msg in msgs:
                    if not isinstance(msg, dict):
                        continue
                    text_obj = msg.get("text") if isinstance(msg.get("text"), dict) else {}
                    out.append({
                        "provider": "meta_cloud",
                        "from": _s(msg.get("from")),
                        "message_id": _s(msg.get("id")),
                        "type": _s(msg.get("type")),
                        "text": _s(text_obj.get("body")),
                        "timestamp": _s(msg.get("timestamp")),
                    })
        return out

    def _dispatch_text_command(self, text: str) -> Dict[str, Any]:
        raw = _s(text)
        low = raw.lower()
        if low.startswith("/help") or low == "help":
            return {"text": "Comandi: /status, /route <msg>, /chat <msg>", "type": "help"}
        if low.startswith("/status"):
            st = model_control_plane.status()
            return {"text": f"RTH ok | providers={st.get('providers_total')} enabled={st.get('providers_enabled')} catalog={st.get('catalog_models')}", "type": "status"}
        if low.startswith("/route "):
            prompt = raw.split(" ", 1)[1].strip()
            rs = model_control_plane.route_explain({"message": prompt, "task_class": "chat_general", "privacy_mode": "allow_cloud"})
            return {"text": f"route {rs.get('status')} | {(rs.get('selected') or {}).get('ref')}", "type": "route"}
        if low.startswith("/chat "):
            prompt = raw.split(" ", 1)[1].strip()
            rs = model_control_plane.chat_execute({
                "message": prompt,
                "task_class": "chat_general",
                "privacy_mode": "allow_cloud",
                "confirm_owner": True,
                "decided_by": "owner",
                "reason": "WhatsApp remote chat",
                "max_tokens": 500,
                "timeout_sec": 60,
            })
            return {"text": _s(rs.get("assistant_message") or rs.get("assistant_preview") or rs.get("status"))[:3500], "type": "chat"}
        return {"text": "Comando non riconosciuto. Usa /help", "type": "unknown"}

    def send_text(self, to: str, text: str, timeout_sec: float = 20.0) -> Dict[str, Any]:
        cfg = self._cfg()
        if cfg["provider"] == "twilio":
            return self._send_text_twilio(to, text, timeout_sec=timeout_sec)
        return self._send_text_meta(to, text, timeout_sec=timeout_sec)

    def _send_text_by_mode(self, to: str, text: str, mode: str = "live", timeout_sec: float = 20.0) -> Dict[str, Any]:
        if _s(mode).lower() == "replay":
            return {
                "status": "ok",
                "mode": "replay",
                "provider": self._cfg().get("provider"),
                "to": to,
                "text_preview": _s(text)[:500],
                "sent_at": _now(),
            }
        return self.send_text(to, text, timeout_sec=timeout_sec)

    def _send_text_meta(self, to: str, text: str, timeout_sec: float = 20.0) -> Dict[str, Any]:
        meta = self._cfg()["meta"]
        token = _s(meta.get("access_token"))
        phone_id = _s(meta.get("phone_number_id"))
        if not token or not phone_id:
            return {"status": "missing_config", "detail": "Meta access token / phone_number_id missing"}
        allowed = set(meta.get("allowed_numbers") or [])
        if allowed and _s(to) not in allowed:
            return {"status": "denied", "detail": "destination not allowlisted", "to": to}
        url = f"https://graph.facebook.com/v21.0/{phone_id}/messages"
        payload = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text[:3500]}}
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "RTH-Core/0.1 (+WhatsAppBridgeMeta)",
        }
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                body = json.loads(raw) if raw.strip() else {}
                return {"status": "ok", "provider": "meta_cloud", "response": body}
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", errors="replace")[:1200]
            except Exception:
                pass
            return {"status": "error", "provider": "meta_cloud", "error": str(e), "status_code": getattr(e, "code", None), "detail": detail}
        except Exception as e:
            return {"status": "error", "provider": "meta_cloud", "error": str(e)}

    def _send_text_twilio(self, to: str, text: str, timeout_sec: float = 20.0) -> Dict[str, Any]:
        tw = self._cfg()["twilio"]
        sid = _s(tw.get("account_sid"))
        token = _s(tw.get("auth_token"))
        from_number = _s(tw.get("from_number"))
        if not sid or not token or not from_number:
            return {"status": "missing_config", "detail": "Twilio SID/token/from missing"}
        allowed = set(tw.get("allowed_numbers") or [])
        if allowed and _s(to) not in allowed:
            return {"status": "denied", "detail": "destination not allowlisted", "to": to}
        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        form = urllib.parse.urlencode({"From": from_number, "To": to, "Body": text[:3500]}).encode("utf-8")
        auth = base64.b64encode(f"{sid}:{token}".encode("utf-8")).decode("ascii")
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {auth}",
            "User-Agent": "RTH-Core/0.1 (+WhatsAppBridgeTwilio)",
        }
        try:
            req = urllib.request.Request(url, data=form, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                body = json.loads(raw) if raw.strip().startswith("{") else {"raw": raw[:800]}
                return {"status": "ok", "provider": "twilio", "response": body}
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", errors="replace")[:1200]
            except Exception:
                pass
            return {"status": "error", "provider": "twilio", "error": str(e), "status_code": getattr(e, "code", None), "detail": detail}
        except Exception as e:
            return {"status": "error", "provider": "twilio", "error": str(e)}


whatsapp_bridge = WhatsAppBridge()
