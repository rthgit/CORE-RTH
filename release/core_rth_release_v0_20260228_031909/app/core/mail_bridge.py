"""
Mail bridge: remote command intake via email, governed by Guardian (permission_gate).

Default posture is safe:
- accept only allowlisted senders
- require a shared secret in the command payload
- execute nothing by default: only creates proposals and sends back request_id(s)

If you later enable remote approvals, keep it scope-limited and risk-limited.
"""

from __future__ import annotations

import json
import logging
import os
import re
import smtplib
import tempfile
from dataclasses import dataclass
from datetime import datetime
from email import message_from_bytes
from email.message import Message
from email.utils import parseaddr
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import imaplib

from .config import settings
from .permissions import permission_gate
from .secret_store import secret_store

logger = logging.getLogger(__name__)


def _choose_state_dir() -> Path:
    candidates = [
        Path("storage") / "mail",
        Path("storage_runtime") / "mail",
        Path(tempfile.gettempdir()) / "rth_core" / "mail",
    ]
    for base in candidates:
        try:
            base.mkdir(parents=True, exist_ok=True)
            probe = base / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return base
        except Exception:
            continue
    p = Path(tempfile.gettempdir()) / "rth_core" / "mail"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _extract_text_body(msg: Message) -> str:
    if msg.is_multipart():
        parts = []
        for part in msg.walk():
            ctype = (part.get_content_type() or "").lower()
            disp = (part.get("Content-Disposition") or "").lower()
            if "attachment" in disp:
                continue
            if ctype == "text/plain":
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                try:
                    parts.append(payload.decode(charset, errors="replace"))
                except Exception:
                    parts.append(payload.decode("utf-8", errors="replace"))
        return "\n".join(parts).strip()
    payload = msg.get_payload(decode=True) or b""
    charset = msg.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace").strip()
    except Exception:
        return payload.decode("utf-8", errors="replace").strip()


def _parse_json_from_body(body: str) -> Optional[Dict[str, Any]]:
    body = body.strip()
    if body.startswith("{") and body.endswith("}"):
        try:
            return json.loads(body)
        except Exception:
            return None

    # Try to find a JSON object block inside the text.
    m = re.search(r"(\{.*\})", body, flags=re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def _normalize_sender(addr: str) -> str:
    return addr.strip().lower()


@dataclass
class MailBridgeConfig:
    imap_host: str
    imap_port: int
    imap_user: str
    imap_password: str
    imap_folder: str
    allowed_senders: List[str]
    shared_secret: str
    allow_remote_approve: bool
    remote_approve_max_risk: str

    @staticmethod
    def from_env() -> Optional["MailBridgeConfig"]:
        imap_host = os.getenv("RTH_IMAP_HOST", "").strip()
        imap_user = secret_store.resolve_env("RTH_IMAP_USER", "channels/mail/imap_user")
        imap_password = secret_store.resolve_env("RTH_IMAP_PASSWORD", "channels/mail/imap_password")
        shared_secret = secret_store.resolve_env("RTH_MAIL_SHARED_SECRET", "channels/mail/shared_secret")

        if not imap_host or not imap_user or not imap_password or not shared_secret:
            return None

        imap_port = int(os.getenv("RTH_IMAP_PORT", "993").strip() or "993")
        imap_folder = os.getenv("RTH_IMAP_FOLDER", "INBOX").strip() or "INBOX"
        allowed = [
            _normalize_sender(x)
            for x in (os.getenv("RTH_MAIL_ALLOWED_SENDERS", "").split(","))
            if x.strip()
        ]
        allow_remote_approve = os.getenv("RTH_MAIL_ALLOW_APPROVE", "0").lower() in ("1", "true", "yes")
        remote_approve_max_risk = (os.getenv("RTH_MAIL_MAX_RISK", "low") or "low").strip().lower()

        return MailBridgeConfig(
            imap_host=imap_host,
            imap_port=imap_port,
            imap_user=imap_user,
            imap_password=imap_password,
            imap_folder=imap_folder,
            allowed_senders=allowed,
            shared_secret=shared_secret,
            allow_remote_approve=allow_remote_approve,
            remote_approve_max_risk=remote_approve_max_risk,
        )


class MailBridge:
    def __init__(self):
        self._state_dir = _choose_state_dir()
        self._state_path = self._state_dir / "mail_bridge_state.json"
        self._state = self._load_state()

    def status(self) -> Dict[str, Any]:
        cfg = MailBridgeConfig.from_env()
        return {
            "module": "mail_bridge",
            "configured": bool(cfg),
            "state_dir": str(self._state_dir),
            "last_poll_at": self._state.get("last_poll_at"),
            "seen_uids_count": len(self._state.get("seen_uids", [])),
            "allow_remote_approve": bool(cfg.allow_remote_approve) if cfg else False,
            "remote_approve_max_risk": cfg.remote_approve_max_risk if cfg else None,
        }

    def poll_once(self, limit: int = 20) -> Dict[str, Any]:
        cfg = MailBridgeConfig.from_env()
        if not cfg:
            return {
                "status": "not_configured",
                "detail": "Missing env vars: RTH_IMAP_HOST/RTH_IMAP_USER/RTH_IMAP_PASSWORD/RTH_MAIL_SHARED_SECRET",
            }

        results = []
        errors = []
        processed = 0

        try:
            imap = imaplib.IMAP4_SSL(cfg.imap_host, cfg.imap_port)
            imap.login(cfg.imap_user, cfg.imap_password)
            imap.select(cfg.imap_folder)

            typ, data = imap.search(None, "UNSEEN")
            if typ != "OK":
                return {"status": "error", "detail": "IMAP search failed"}
            uids = [x for x in (data[0] or b"").split() if x]
            uids = uids[: max(0, int(limit))]

            for uid in uids:
                uid_s = uid.decode("utf-8", errors="replace")
                if uid_s in set(self._state.get("seen_uids", [])):
                    continue
                processed += 1
                try:
                    typ2, msg_data = imap.fetch(uid, "(RFC822)")
                    if typ2 != "OK" or not msg_data or not msg_data[0]:
                        errors.append({"uid": uid_s, "error": "fetch_failed"})
                        self._mark_seen(uid_s)
                        continue

                    raw_bytes = msg_data[0][1]
                    msg = message_from_bytes(raw_bytes)

                    out = self._handle_message(msg, cfg)
                    results.append({"uid": uid_s, **out})
                except Exception as e:
                    errors.append({"uid": uid_s, "error": str(e)})
                finally:
                    self._mark_seen(uid_s)

            imap.logout()
        except Exception as e:
            return {"status": "error", "error": str(e)}

        self._state["last_poll_at"] = datetime.now().isoformat()
        self._save_state()

        return {
            "status": "ok",
            "processed": processed,
            "results": results,
            "errors": errors,
        }

    def _handle_message(self, msg: Message, cfg: MailBridgeConfig) -> Dict[str, Any]:
        from_addr = _normalize_sender(parseaddr(msg.get("From", "") or "")[1])
        subject = (msg.get("Subject") or "").strip()
        message_id = (msg.get("Message-ID") or "").strip()
        body = _extract_text_body(msg)
        payload = _parse_json_from_body(body)

        return self._handle_payload(
            payload=payload,
            from_addr=from_addr,
            subject=subject,
            message_id=message_id,
            cfg=cfg,
            send_reply=True,
        )

    def replay_payload(
        self,
        payload: Dict[str, Any],
        from_addr: str = "owner@example.local",
        subject: str = "[RTH Replay]",
        shared_secret: str = "rth-replay-secret",
        allow_remote_approve: bool = False,
        remote_approve_max_risk: str = "low",
    ) -> Dict[str, Any]:
        from_norm = _normalize_sender(from_addr or "owner@example.local")
        pl = dict(payload or {})
        if "secret" not in pl:
            pl["secret"] = shared_secret
        cfg = MailBridgeConfig(
            imap_host="replay.local",
            imap_port=993,
            imap_user="replay",
            imap_password="replay",
            imap_folder="INBOX",
            allowed_senders=[from_norm],
            shared_secret=shared_secret,
            allow_remote_approve=bool(allow_remote_approve),
            remote_approve_max_risk=(remote_approve_max_risk or "low").strip().lower(),
        )
        out = self._handle_payload(
            payload=pl,
            from_addr=from_norm,
            subject=subject,
            message_id=f"<replay-{int(datetime.now().timestamp())}@rth.local>",
            cfg=cfg,
            send_reply=False,
        )
        self._state["last_poll_at"] = datetime.now().isoformat()
        self._save_state()
        return {"status": "ok", "mode": "replay", "mail_bridge": self.status(), "input": {"from": from_norm, "subject": subject}, "result": out}

    def _handle_payload(
        self,
        payload: Optional[Dict[str, Any]],
        from_addr: str,
        subject: str,
        message_id: str,
        cfg: MailBridgeConfig,
        send_reply: bool,
    ) -> Dict[str, Any]:
        from_addr = _normalize_sender(from_addr)

        if cfg.allowed_senders and from_addr not in set(cfg.allowed_senders):
            return {"status": "rejected", "reason": "sender_not_allowed", "from": from_addr, "subject": subject}

        if not payload:
            return {"status": "rejected", "reason": "missing_json_payload", "from": from_addr, "subject": subject}

        if str(payload.get("secret", "")).strip() != cfg.shared_secret:
            return {"status": "rejected", "reason": "bad_secret", "from": from_addr, "subject": subject}

        cmd = str(payload.get("cmd", "")).strip().lower()
        if not cmd:
            return {"status": "rejected", "reason": "missing_cmd", "from": from_addr, "subject": subject}

        # Only a small allowlist of commands.
        if cmd in ("status", "capabilities"):
            out = self._cmd_status(cmd)
        elif cmd == "plugin_runtime_propose":
            out = self._cmd_plugin_runtime_propose(payload)
        elif cmd == "plugin_runtime_run":
            out = self._cmd_plugin_runtime_run(payload, cfg)
        elif cmd == "workspace_propose":
            out = self._cmd_workspace_propose(payload)
        elif cmd == "workspace_run":
            out = self._cmd_workspace_run(payload, cfg)
        elif cmd == "governance_list":
            out = self._cmd_governance_list(payload)
        else:
            out = {"status": "rejected", "reason": "cmd_not_allowed", "cmd": cmd}

        # Best-effort email reply (optional), disabled in replay mode.
        if send_reply:
            self._maybe_reply(from_addr, subject, message_id, out)

        return {
            "status": "handled",
            "from": from_addr,
            "subject": subject,
            "message_id": message_id,
            "cmd": cmd,
            "result": out,
        }

    def _cmd_status(self, cmd: str) -> Dict[str, Any]:
        from .jarvis import jarvis_core

        if cmd == "capabilities":
            return {"status": "ok", "capabilities": jarvis_core.capabilities()}
        return {"status": "ok", "jarvis_status": jarvis_core.get_status(), "mail_bridge": self.status()}

    def _cmd_plugin_runtime_propose(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        from .jarvis import jarvis_core

        reason = str(payload.get("reason") or "Mail request: plugin runtime cycle")
        return {"status": "ok", "proposal": jarvis_core.plugin_runtime_propose(reason=reason)}

    def _cmd_plugin_runtime_run(self, payload: Dict[str, Any], cfg: MailBridgeConfig) -> Dict[str, Any]:
        if not cfg.allow_remote_approve:
            return {"status": "rejected", "reason": "remote_approve_disabled"}

        from .jarvis import jarvis_core

        request_id = str(payload.get("request_id") or "").strip()
        if not request_id:
            return {"status": "rejected", "reason": "missing_request_id"}

        # Risk-gate: refuse if request risk is above max.
        req = permission_gate.requests.get(request_id)
        if not req:
            return {"status": "rejected", "reason": "unknown_request_id"}
        if not self._risk_allowed(req.risk.value, cfg.remote_approve_max_risk):
            return {"status": "rejected", "reason": "risk_too_high", "risk": req.risk.value, "max": cfg.remote_approve_max_risk}

        return {"status": "ok", "report": jarvis_core.plugin_runtime_run(request_id=request_id, min_score=float(payload.get("min_score", 0.0)))}

    def _cmd_workspace_propose(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        from .jarvis import jarvis_core

        workspace = str(payload.get("workspace") or "").strip()
        action = str(payload.get("action") or "").strip()
        reason = str(payload.get("reason") or f"Mail request: workspace {workspace} {action}")
        command = payload.get("command")
        return {"status": "ok", "proposal": jarvis_core.workspace_propose(workspace=workspace, action=action, reason=reason, command=command)}

    def _cmd_workspace_run(self, payload: Dict[str, Any], cfg: MailBridgeConfig) -> Dict[str, Any]:
        if not cfg.allow_remote_approve:
            return {"status": "rejected", "reason": "remote_approve_disabled"}

        from .jarvis import jarvis_core

        request_id = str(payload.get("request_id") or "").strip()
        if not request_id:
            return {"status": "rejected", "reason": "missing_request_id"}

        req = permission_gate.requests.get(request_id)
        if not req:
            return {"status": "rejected", "reason": "unknown_request_id"}
        if not self._risk_allowed(req.risk.value, cfg.remote_approve_max_risk):
            return {"status": "rejected", "reason": "risk_too_high", "risk": req.risk.value, "max": cfg.remote_approve_max_risk}

        return {"status": "ok", "job": jarvis_core.workspace_approve_and_execute(request_id=request_id, decided_by="mail_owner")}

    def _cmd_governance_list(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        from .jarvis import jarvis_core

        status = payload.get("status")
        return {"status": "ok", "governance": jarvis_core.governance_list(status=status)}

    def _risk_allowed(self, risk: str, max_risk: str) -> bool:
        # low < medium < high
        order = {"low": 0, "medium": 1, "high": 2}
        return order.get(risk, 2) <= order.get(max_risk, 0)

    def _maybe_reply(self, to_addr: str, subject: str, in_reply_to: str, out: Dict[str, Any]) -> None:
        # Uses existing SMTP settings if present; if not configured, skip silently.
        smtp_user = settings.SMTP_USER or secret_store.resolve_env("SMTP_USER", "channels/mail/smtp_user")
        smtp_password = settings.SMTP_PASSWORD or secret_store.resolve_env("SMTP_PASSWORD", "channels/mail/smtp_password")
        from_email = settings.EMAILS_FROM_EMAIL or os.getenv("EMAILS_FROM_EMAIL", "").strip()
        if not settings.SMTP_HOST or not smtp_user or not smtp_password or not from_email:
            return
        try:
            reply_subject = f"[RTH] Re: {subject}" if subject else "[RTH] Reply"
            payload = json.dumps(out, indent=2, default=str)
            msg = (
                f"From: {settings.EMAILS_FROM_NAME} <{from_email}>\r\n"
                f"To: {to_addr}\r\n"
                f"Subject: {reply_subject}\r\n"
                f"In-Reply-To: {in_reply_to}\r\n"
                f"Date: {datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')}\r\n"
                f"Content-Type: text/plain; charset=utf-8\r\n"
                f"\r\n"
                f"{payload}\r\n"
            )

            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20)
            try:
                if settings.SMTP_TLS:
                    server.starttls()
                server.login(smtp_user, smtp_password)
                server.sendmail(from_email, [to_addr], msg.encode("utf-8"))
            finally:
                try:
                    server.quit()
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"MailBridge reply failed: {e}")

    def _load_state(self) -> Dict[str, Any]:
        try:
            if self._state_path.exists():
                return json.loads(self._state_path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {"seen_uids": [], "last_poll_at": None}

    def _save_state(self) -> None:
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            self._state_path.write_text(json.dumps(self._state, indent=2, default=str), encoding="utf-8")
        except Exception:
            pass

    def _mark_seen(self, uid: str) -> None:
        seen = list(self._state.get("seen_uids", []))
        if uid in seen:
            return
        seen.append(uid)
        # cap memory growth
        self._state["seen_uids"] = seen[-2000:]


mail_bridge = MailBridge()
