from __future__ import annotations

import base64
import ctypes
import json
import os
from ctypes import wintypes
from pathlib import Path
from typing import Protocol


class SecretProtector(Protocol):
    def protect(self, plaintext: bytes) -> bytes: ...

    def unprotect(self, ciphertext: bytes) -> bytes: ...


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _blob(data: bytes) -> tuple[_DataBlob, ctypes.Array]:
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    return _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))), buffer


class WindowsDPAPIProtector:
    """Encrypt secrets for the current Windows user via CryptProtectData."""

    _UI_FORBIDDEN = 0x01

    def __init__(self) -> None:
        if os.name != "nt":
            raise RuntimeError("Windows DPAPI is only available on Windows")
        self._crypt32 = ctypes.windll.crypt32
        self._kernel32 = ctypes.windll.kernel32

    def protect(self, plaintext: bytes) -> bytes:
        return self._transform(plaintext, decrypt=False)

    def unprotect(self, ciphertext: bytes) -> bytes:
        return self._transform(ciphertext, decrypt=True)

    def _transform(self, data: bytes, *, decrypt: bool) -> bytes:
        if not data:
            raise ValueError("DPAPI input cannot be empty")
        input_blob, input_buffer = _blob(data)
        output_blob = _DataBlob()
        function = self._crypt32.CryptUnprotectData if decrypt else self._crypt32.CryptProtectData
        if decrypt:
            success = function(
                ctypes.byref(input_blob),
                None,
                None,
                None,
                None,
                self._UI_FORBIDDEN,
                ctypes.byref(output_blob),
            )
        else:
            success = function(
                ctypes.byref(input_blob),
                "AI Job Orchestrator CN",
                None,
                None,
                None,
                self._UI_FORBIDDEN,
                ctypes.byref(output_blob),
            )
        _ = input_buffer  # keep the backing storage alive for the native call
        if not success:
            raise ctypes.WinError()
        try:
            return ctypes.string_at(output_blob.pbData, output_blob.cbData)
        finally:
            self._kernel32.LocalFree(output_blob.pbData)


class EncryptedSecretStore:
    def __init__(self, path: Path, protector: SecretProtector) -> None:
        self.path = path
        self.protector = protector

    def set(self, key: str, value: str) -> None:
        if not key or not value:
            raise ValueError("secret key and value must be non-empty")
        values = self._read()
        encrypted = self.protector.protect(value.encode("utf-8"))
        values[key] = base64.b64encode(encrypted).decode("ascii")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps(values, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def get(self, key: str) -> str | None:
        encoded = self._read().get(key)
        if encoded is None:
            return None
        decrypted = self.protector.unprotect(base64.b64decode(encoded, validate=True))
        return decrypted.decode("utf-8")

    def delete(self, key: str) -> None:
        values = self._read()
        if key not in values:
            return
        del values[key]
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def _read(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in payload.items()
        ):
            raise ValueError("invalid encrypted secret store")
        return payload

