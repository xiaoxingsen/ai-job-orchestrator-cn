import json
import sys

import pytest
from job_orchestrator.security.secrets import EncryptedSecretStore, WindowsDPAPIProtector


@pytest.mark.skipif(sys.platform != "win32", reason="Windows DPAPI test")
def test_dpapi_round_trip_does_not_return_plaintext_ciphertext() -> None:
    protector = WindowsDPAPIProtector()
    plaintext = b"sk-local-test-secret"

    ciphertext = protector.protect(plaintext)

    assert ciphertext != plaintext
    assert plaintext not in ciphertext
    assert protector.unprotect(ciphertext) == plaintext


@pytest.mark.skipif(sys.platform != "win32", reason="Windows DPAPI test")
def test_secret_store_never_writes_api_key_in_plaintext(tmp_path) -> None:
    path = tmp_path / "secrets.json"
    store = EncryptedSecretStore(path, WindowsDPAPIProtector())

    store.set("openai_compatible", "sk-sensitive-value")

    raw = path.read_text(encoding="utf-8")
    assert "sk-sensitive-value" not in raw
    assert store.get("openai_compatible") == "sk-sensitive-value"
    assert set(json.loads(raw)) == {"openai_compatible"}

