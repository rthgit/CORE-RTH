"""
Security Vault — Zero-Key Storage for Core Rth.

Provides transparent AES-256-GCM encryption for sensitive data at rest
(e.g., secrets, agent threads, telemetry).

Key Derivation Strategy:
1. Primary: OS Keyring (Windows Credential Manager, macOS Keychain, Linux Secret Service).
2. Fallback: Hardware ID (MAC address + fixed salt) hash if running headless.

The Master Key is NEVER stored on disk in plaintext.
All encrypted files use a magic header `RTHV1` followed by a random 12-byte nonce
and the 16-byte GCM auth tag, plus the ciphertext.
"""
from __future__ import annotations

import json
import logging
import os
import platform
import uuid
import hashlib
from typing import Any, Dict, Optional, Union
from pathlib import Path

logger = logging.getLogger(__name__)

_KEYRING_SVC = "CORE_RTH_SECURITY_VAULT"
_KEYRING_USER = "master_key"
_MAGIC_HEADER = b"RTHV1"


class SecurityVault:
    """Handles transparent encryption/decryption of data at rest."""

    def __init__(self):
        self._master_key: Optional[bytes] = None
        self._available = False
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            self._AESGCM = AESGCM
            self._available = True
        except ImportError:
            logger.warning("cryptography not installed — Security Vault disabled.")

    @property
    def available(self) -> bool:
        return self._available

    def _get_hw_id(self) -> str:
        """Derive a consistent hardware ID for fallback."""
        try:
            # cross-platform simple HW id -> MAC address
            mac = uuid.getnode()
            if (mac >> 40) % 2:
                # multicast MAC means it's randomized, fallback to hostname + platform
                return f"{platform.node()}_{platform.system()}_{platform.machine()}"
            return str(mac)
        except Exception:
            return "fallback_hw_id_123456"

    def _derive_fallback_key(self) -> bytes:
        hwid = self._get_hw_id()
        salt = b"core_rth_fallback_salt_2026"
        # Derive 32 bytes (256-bit) key
        return hashlib.pbkdf2_hmac("sha256", hwid.encode(), salt, 100000, 32)

    def _init_key(self):
        """Initialize or retrieve the master key."""
        if self._master_key:
            return

        # Attempt to use OS Keyring
        try:
            import keyring
            stored_key_hex = keyring.get_password(_KEYRING_SVC, _KEYRING_USER)
            if stored_key_hex:
                self._master_key = bytes.fromhex(stored_key_hex)
                logger.debug("Master key retrieved from OS Keyring.")
                return

            # If not present, generate and store
            new_key = os.urandom(32)
            keyring.set_password(_KEYRING_SVC, _KEYRING_USER, new_key.hex())
            self._master_key = new_key
            logger.debug("New master key generated and stored in OS Keyring.")
            return

        except Exception as e:
            logger.info(f"OS Keyring unavailable ({e}), using Hardware ID fallback.")

        # Fallback to Hardware ID
        self._master_key = self._derive_fallback_key()

    # ── Core Crypto ──────────────────────────────────────────────────

    def encrypt(self, data: bytes) -> bytes:
        """Encrypt raw bytes using AES-256-GCM."""
        if not self._available:
            return data
        self._init_key()
        aesgcm = self._AESGCM(self._master_key)
        nonce = os.urandom(12)
        ct = aesgcm.encrypt(nonce, data, None)
        return _MAGIC_HEADER + nonce + ct

    def decrypt(self, encrypted_data: bytes) -> bytes:
        """Decrypt raw bytes using AES-256-GCM."""
        if not self._available:
            return encrypted_data
        
        if not encrypted_data.startswith(_MAGIC_HEADER):
            # Not encrypted by us, return as is (transparent fallback)
            return encrypted_data

        self._init_key()
        aesgcm = self._AESGCM(self._master_key)
        
        header_len = len(_MAGIC_HEADER)
        nonce = encrypted_data[header_len:header_len+12]
        ct = encrypted_data[header_len+12:]
        
        try:
            return aesgcm.decrypt(nonce, ct, None)
        except Exception as e:
            logger.error(f"Decryption failed (corrupted or wrong key): {e}")
            raise ValueError("Data decryption failed") from e

    # ── Helpers for Strings & JSON ───────────────────────────────────

    def encrypt_string(self, text: str) -> str:
        """Encrypt a string and return hex representation."""
        if not self._available:
            return text
        enc = self.encrypt(text.encode("utf-8"))
        return enc.hex()

    def decrypt_string(self, hex_text: str) -> str:
        """Decrypt a hex string."""
        if not self._available:
            return hex_text
        try:
            raw = bytes.fromhex(hex_text)
            return self.decrypt(raw).decode("utf-8")
        except ValueError:
            # Might not be hex or not encrypted
            return hex_text

    def encrypt_json(self, data: Union[Dict, list]) -> bytes:
        """Serialize Dict/List to JSON and encrypt."""
        raw = json.dumps(data, default=str).encode("utf-8")
        return self.encrypt(raw)

    def decrypt_json(self, encrypted_data: bytes) -> Union[Dict, list]:
        """Decrypt bytes and deserialize JSON."""
        raw = self.decrypt(encrypted_data)
        return json.loads(raw.decode("utf-8"))

    # ── File Operations ──────────────────────────────────────────────

    def encrypt_file(self, filepath: Union[str, Path], data: Any):
        """
        Encrypt data and save to file. 
        If data is dict/list, it's treated as JSON. Otherwise treated as string.
        """
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        if isinstance(data, (dict, list)):
            payload = self.encrypt_json(data)
        else:
            payload = self.encrypt(str(data).encode("utf-8"))
            
        path.write_bytes(payload)

    def decrypt_file(self, filepath: Union[str, Path], as_json: bool = False) -> Any:
        """Read and decrypt a file."""
        path = Path(filepath)
        if not path.exists():
            return None
        
        payload = path.read_bytes()
        
        if as_json:
            try:
                return self.decrypt_json(payload)
            except Exception:
                # Fallback if the file was saved unencrypted before this feature
                return json.loads(payload.decode("utf-8"))
        else:
            try:
                return self.decrypt(payload).decode("utf-8")
            except Exception:
                return payload.decode("utf-8")


# Singleton
security_vault = SecurityVault()
