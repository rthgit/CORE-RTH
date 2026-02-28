"""
Local secret store v0.

Priority order:
1) `keyring` backend (if available and functional)
2) Windows DPAPI-encrypted local file
3) Obfuscated local file fallback (base64, not secure)

This module is designed for local/dev use and API key hygiene. It avoids returning
secret values from status/list APIs. Callers should use `get()` only when they need
to execute a request.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
import base64
import ctypes
import ctypes.wintypes as wintypes
import json
import logging
import os
import tempfile
import hashlib

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _s(v: Any) -> str:
    return str(v or "").strip()


def _mask(secret: str) -> str:
    s = _s(secret)
    if not s:
        return ""
    if len(s) <= 8:
        return "*" * len(s)
    return f"{s[:3]}{'*' * max(4, len(s)-7)}{s[-4:]}"


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


class SecretStore:
    def __init__(self) -> None:
        self._service_name = "rth_core"
        self._meta_path = self._resolve_meta_path()
        self._audit_path = self._meta_path.with_name("secret_store_audit.jsonl")
        self._keyring = self._try_keyring()
        self._mode = self._detect_mode()
        self._state = self._load_state()

    def status(self) -> Dict[str, Any]:
        self._state = self._load_state()
        names = sorted(list((self._state.get("entries") or {}).keys()))
        return {
            "status": "ok",
            "module": "secret_store",
            "mode": self._mode,
            "meta_path": str(self._meta_path),
            "audit_path": str(self._audit_path),
            "entries_total": len(names),
            "entries": [
                {
                    "name": n,
                    "updated_at": ((self._state.get("entries") or {}).get(n) or {}).get("updated_at"),
                    "has_value": True,
                    "masked": ((self._state.get("entries") or {}).get(n) or {}).get("masked", ""),
                    "backend": ((self._state.get("entries") or {}).get(n) or {}).get("backend", self._mode),
                }
                for n in names[:200]
            ],
            "timestamp": _now(),
        }

    def list_names(self) -> Dict[str, Any]:
        return self.status()

    def has(self, name: str) -> bool:
        nm = self._normalize_name(name)
        if not nm:
            return False
        meta = (self._load_state().get("entries") or {}).get(nm)
        if not isinstance(meta, dict):
            return False
        if meta.get("backend") == "keyring":
            try:
                return bool(_s(self._keyring.get_password(self._service_name, nm))) if self._keyring else False
            except Exception:
                return False
        if meta.get("backend") in {"file_dpapi", "file_obfuscated"}:
            return bool(_s(meta.get("ciphertext")))
        return False

    def masked(self, name: str) -> str:
        nm = self._normalize_name(name)
        meta = (self._load_state().get("entries") or {}).get(nm) or {}
        return _s(meta.get("masked"))

    def set(self, name: str, value: str, actor: str = "owner", reason: str = "") -> Dict[str, Any]:
        nm = self._normalize_name(name)
        val = _s(value)
        if not nm:
            return {"status": "invalid", "error": "name_required"}
        if not val:
            return {"status": "invalid", "error": "value_required"}
        st = self._load_state()
        entries = st.setdefault("entries", {})
        meta: Dict[str, Any] = {
            "updated_at": _now(),
            "masked": _mask(val),
            "backend": self._mode,
        }
        try:
            if self._mode == "keyring":
                if not self._keyring:
                    return {"status": "error", "error": "keyring_not_available"}
                self._keyring.set_password(self._service_name, nm, val)
                meta["keyring_account"] = nm
                meta.pop("ciphertext", None)
            elif self._mode == "file_dpapi":
                meta["ciphertext"] = self._dpapi_encrypt(val)
            else:
                meta["ciphertext"] = base64.b64encode(val.encode("utf-8")).decode("ascii")
            entries[nm] = meta
            st["updated_at"] = _now()
            self._save_state(st)
            self._state = st
            out = {"status": "ok", "name": nm, "backend": self._mode, "masked": meta["masked"]}
            self._audit("set", nm, out["status"], actor=actor, reason=reason, extra={"backend": self._mode})
            return out
        except Exception as e:
            logger.warning(f"SecretStore set failed for {nm}: {e}")
            out = {"status": "error", "name": nm, "error": str(e)}
            self._audit("set", nm, out["status"], actor=actor, reason=reason, extra={"error": str(e)})
            return out

    def get(self, name: str, default: str = "") -> str:
        nm = self._normalize_name(name)
        if not nm:
            return default
        meta = (self._load_state().get("entries") or {}).get(nm)
        if not isinstance(meta, dict):
            return default
        try:
            backend = _s(meta.get("backend")) or self._mode
            if backend == "keyring":
                if not self._keyring:
                    return default
                return _s(self._keyring.get_password(self._service_name, nm)) or default
            if backend == "file_dpapi":
                return self._dpapi_decrypt(_s(meta.get("ciphertext"))) or default
            if backend == "file_obfuscated":
                raw = base64.b64decode(_s(meta.get("ciphertext")).encode("ascii"))
                return raw.decode("utf-8", errors="replace") or default
        except Exception as e:
            logger.warning(f"SecretStore get failed for {nm}: {e}")
        return default

    def delete(self, name: str, actor: str = "owner", reason: str = "") -> Dict[str, Any]:
        nm = self._normalize_name(name)
        if not nm:
            return {"status": "invalid", "error": "name_required"}
        st = self._load_state()
        entries = st.setdefault("entries", {})
        meta = entries.get(nm)
        if not isinstance(meta, dict):
            return {"status": "not_found", "name": nm}
        try:
            if _s(meta.get("backend")) == "keyring" and self._keyring:
                try:
                    self._keyring.delete_password(self._service_name, nm)
                except Exception:
                    pass
            entries.pop(nm, None)
            st["updated_at"] = _now()
            self._save_state(st)
            self._state = st
            out = {"status": "ok", "name": nm}
            self._audit("delete", nm, out["status"], actor=actor, reason=reason)
            return out
        except Exception as e:
            logger.warning(f"SecretStore delete failed for {nm}: {e}")
            out = {"status": "error", "name": nm, "error": str(e)}
            self._audit("delete", nm, out["status"], actor=actor, reason=reason, extra={"error": str(e)})
            return out

    def rotate(self, name: str, new_value: str, keep_previous: bool = True, actor: str = "owner", reason: str = "") -> Dict[str, Any]:
        nm = self._normalize_name(name)
        if not nm:
            return {"status": "invalid", "error": "name_required"}
        new_val = _s(new_value)
        if not new_val:
            return {"status": "invalid", "error": "value_required"}
        old_exists = self.has(nm)
        archived_name = None
        if keep_previous and old_exists:
            old_val = self.get(nm, default="")
            if old_val:
                suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
                archived_name = f"{nm}/_rotated/{suffix}"
                self.set(archived_name, old_val, actor=actor, reason=f"rotation_archive:{nm}")
        res = self.set(nm, new_val, actor=actor, reason=reason or "rotate")
        out = {
            "status": res.get("status"),
            "name": nm,
            "rotated": True,
            "previous_existed": old_exists,
            "archived_name": archived_name,
            "backend": res.get("backend"),
            "masked": res.get("masked"),
        }
        self._audit("rotate", nm, out["status"], actor=actor, reason=reason, extra={"archived_name": archived_name, "keep_previous": bool(keep_previous)})
        return out

    def export_bundle(self, include_values: bool = False, actor: str = "owner", reason: str = "") -> Dict[str, Any]:
        st = self._load_state()
        entries_meta = st.get("entries") if isinstance(st.get("entries"), dict) else {}
        rows = []
        for name in sorted(entries_meta.keys()):
            meta = entries_meta.get(name) if isinstance(entries_meta, dict) else None
            if not isinstance(meta, dict):
                continue
            row = {
                "name": name,
                "updated_at": meta.get("updated_at"),
                "masked": meta.get("masked"),
                "backend": meta.get("backend"),
                "has_value": self.has(name),
            }
            if include_values and row["has_value"]:
                val = self.get(name, default="")
                if val:
                    enc_mode = "dpapi_user" if self._dpapi_supported() else "obfuscated"
                    row["export_enc"] = enc_mode
                    row["export_value"] = self._export_encrypt_value(val, enc_mode)
            rows.append(row)
        bundle: Dict[str, Any] = {
            "format": "rth.secret.export.v1",
            "exported_at": _now(),
            "include_values": bool(include_values),
            "entries": rows,
            "source": {
                "secret_store_mode": self._mode,
                "host_os": os.name,
            },
        }
        payload = json.dumps(bundle, sort_keys=True, ensure_ascii=False).encode("utf-8")
        bundle["checksum_sha256"] = hashlib.sha256(payload).hexdigest()
        self._audit("export", "*", "ok", actor=actor, reason=reason, extra={"include_values": bool(include_values), "entries_total": len(rows)})
        return {"status": "ok", "bundle": bundle, "summary": {"entries_total": len(rows), "include_values": bool(include_values)}}

    def import_bundle(self, bundle: Dict[str, Any], import_values: bool = True, on_conflict: str = "overwrite", actor: str = "owner", reason: str = "") -> Dict[str, Any]:
        if not isinstance(bundle, dict):
            return {"status": "invalid", "error": "bundle_must_be_object"}
        if _s(bundle.get("format")) != "rth.secret.export.v1":
            return {"status": "invalid", "error": "unsupported_format"}
        if not self._verify_export_checksum(bundle):
            return {"status": "invalid", "error": "checksum_mismatch"}
        entries = bundle.get("entries") if isinstance(bundle.get("entries"), list) else []
        imported = []
        skipped = []
        errors = []
        conflict_mode = _s(on_conflict).lower() or "overwrite"
        if conflict_mode not in {"overwrite", "skip"}:
            conflict_mode = "overwrite"
        for row in entries[:1000]:
            if not isinstance(row, dict):
                continue
            name = self._normalize_name(row.get("name") or "")
            if not name:
                continue
            exists = self.has(name)
            if exists and conflict_mode == "skip":
                skipped.append({"name": name, "reason": "exists"})
                continue
            if import_values and row.get("export_value"):
                try:
                    plaintext = self._export_decrypt_value(_s(row.get("export_value")), _s(row.get("export_enc")) or "obfuscated")
                    if not plaintext:
                        errors.append({"name": name, "error": "empty_decrypted_value"})
                        continue
                    res = self.set(name, plaintext, actor=actor, reason=reason or "import")
                    if res.get("status") == "ok":
                        imported.append({"name": name, "mode": "value"})
                    else:
                        errors.append({"name": name, "error": res.get("error") or res.get("status")})
                except Exception as e:
                    errors.append({"name": name, "error": str(e)})
            else:
                skipped.append({"name": name, "reason": "no_value_payload"})
        status = "ok" if not errors else ("partial" if imported else "error")
        out = {"status": status, "imported": imported, "skipped": skipped, "errors": errors, "summary": {"imported": len(imported), "skipped": len(skipped), "errors": len(errors)}}
        self._audit("import", "*", status, actor=actor, reason=reason, extra=out["summary"])
        return out

    def audit(self, limit: int = 100) -> Dict[str, Any]:
        rows = []
        try:
            if self._audit_path.exists():
                for line in self._audit_path.read_text(encoding="utf-8", errors="replace").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        continue
        except Exception as e:
            return {"status": "error", "error": str(e), "audit_path": str(self._audit_path)}
        rows = rows[-max(1, min(int(limit), 1000)):]
        return {"status": "ok", "audit_path": str(self._audit_path), "count": len(rows), "events": rows}

    def resolve_env(self, env_name: str, secret_name: str, default: str = "") -> str:
        val = _s(os.getenv(env_name))
        if val:
            return val
        return self.get(secret_name, default=default)

    # internals
    def _normalize_name(self, name: str) -> str:
        return "/".join([x for x in _s(name).replace("\\", "/").split("/") if x])

    def _resolve_meta_path(self) -> Path:
        raw = _s(os.getenv("RTH_SECRET_STORE_BASE"))
        candidates = []
        if raw:
            p = Path(os.path.expandvars(os.path.expanduser(raw)))
            if p.suffix.lower() == ".json":
                candidates.append(p)
            else:
                candidates.append(p / "secret_store_meta.json")
        candidates.extend(
            [
                Path("storage") / "secrets" / "secret_store_meta.json",
                Path("storage_runtime") / "secrets" / "secret_store_meta.json",
                Path(tempfile.gettempdir()) / "rth_core" / "secrets" / "secret_store_meta.json",
            ]
        )
        for path in candidates:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                probe = path.parent / ".write_probe"
                probe.write_text("ok", encoding="utf-8")
                probe.unlink(missing_ok=True)
                return path
            except Exception:
                continue
        p = Path(tempfile.gettempdir()) / "rth_core" / "secrets" / "secret_store_meta.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def _load_state(self) -> Dict[str, Any]:
        try:
            if self._meta_path.exists():
                from app.core.security_vault import security_vault
                payload = security_vault.decrypt_file(self._meta_path, as_json=True)
                if isinstance(payload, dict):
                    payload.setdefault("entries", {})
                    payload.setdefault("version", 1)
                    payload.setdefault("updated_at", _now())
                    return payload
        except Exception as e:
            logger.warning(f"SecretStore load failed: {e}")
        return {"version": 1, "updated_at": _now(), "entries": {}}

    def _save_state(self, state: Dict[str, Any]) -> None:
        self._meta_path.parent.mkdir(parents=True, exist_ok=True)
        from app.core.security_vault import security_vault
        security_vault.encrypt_file(self._meta_path, state)

    def _audit(self, action: str, name: str, status: str, actor: str = "owner", reason: str = "", extra: Optional[Dict[str, Any]] = None) -> None:
        row = {
            "ts": _now(),
            "action": _s(action),
            "name": self._normalize_name(name) if _s(name) != "*" else "*",
            "status": _s(status),
            "actor": _s(actor) or "owner",
            "reason": _s(reason),
            "extra": extra or {},
        }
        try:
            self._audit_path.parent.mkdir(parents=True, exist_ok=True)
            with self._audit_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"SecretStore audit write failed: {e}")

    def _try_keyring(self):
        try:
            import keyring  # type: ignore

            try:
                # sanity probe: backend object exists and looks usable
                _ = keyring.get_keyring()
                return keyring
            except Exception:
                return None
        except Exception:
            return None

    def _detect_mode(self) -> str:
        forced = _s(os.getenv("RTH_SECRET_STORE_MODE")).lower()
        allowed = {"keyring", "file_dpapi", "file_obfuscated"}
        if forced in allowed:
            if forced == "keyring" and not self._keyring:
                return "file_dpapi" if self._dpapi_supported() else "file_obfuscated"
            if forced == "file_dpapi" and not self._dpapi_supported():
                return "file_obfuscated"
            return forced
        if self._keyring:
            return "keyring"
        if self._dpapi_supported():
            return "file_dpapi"
        return "file_obfuscated"

    def _dpapi_supported(self) -> bool:
        return os.name == "nt" and hasattr(ctypes, "windll") and hasattr(ctypes.windll, "crypt32")

    def _dpapi_encrypt(self, plaintext: str) -> str:
        if not self._dpapi_supported():
            raise RuntimeError("dpapi_not_supported")
        data = plaintext.encode("utf-8")
        in_blob = _DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_byte)))
        out_blob = _DATA_BLOB()
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        CRYPTPROTECT_UI_FORBIDDEN = 0x01
        ok = crypt32.CryptProtectData(
            ctypes.byref(in_blob),
            "RTH Core Secret",
            None,
            None,
            None,
            CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(out_blob),
        )
        if not ok:
            raise ctypes.WinError()
        try:
            buf = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            return base64.b64encode(buf).decode("ascii")
        finally:
            if out_blob.pbData:
                kernel32.LocalFree(out_blob.pbData)

    def _dpapi_decrypt(self, ciphertext_b64: str) -> str:
        if not self._dpapi_supported():
            raise RuntimeError("dpapi_not_supported")
        data = base64.b64decode(ciphertext_b64.encode("ascii"))
        in_blob = _DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_byte)))
        out_blob = _DATA_BLOB()
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        CRYPTPROTECT_UI_FORBIDDEN = 0x01
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(in_blob),
            None,
            None,
            None,
            None,
            CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(out_blob),
        )
        if not ok:
            raise ctypes.WinError()
        try:
            buf = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            return buf.decode("utf-8", errors="replace")
        finally:
            if out_blob.pbData:
                kernel32.LocalFree(out_blob.pbData)

    def _export_encrypt_value(self, plaintext: str, mode: str) -> str:
        m = _s(mode).lower()
        if m == "dpapi_user":
            return self._dpapi_encrypt(plaintext)
        return base64.b64encode(plaintext.encode("utf-8")).decode("ascii")

    def _export_decrypt_value(self, ciphertext: str, mode: str) -> str:
        m = _s(mode).lower()
        if m == "dpapi_user":
            return self._dpapi_decrypt(ciphertext)
        return base64.b64decode(ciphertext.encode("ascii")).decode("utf-8", errors="replace")

    def _verify_export_checksum(self, bundle: Dict[str, Any]) -> bool:
        try:
            expected = _s(bundle.get("checksum_sha256"))
            probe = dict(bundle)
            probe.pop("checksum_sha256", None)
            payload = json.dumps(probe, sort_keys=True, ensure_ascii=False).encode("utf-8")
            actual = hashlib.sha256(payload).hexdigest()
            return bool(expected) and actual == expected
        except Exception:
            return False


secret_store = SecretStore()
