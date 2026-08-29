import pytest
from cryptography.fernet import Fernet

from signal_backend.services import crypto


@pytest.fixture(autouse=True)
def encryption_key(monkeypatch):
    monkeypatch.setattr(crypto.settings, "encryption_key", Fernet.generate_key().decode())


def test_encrypt_decrypt_roundtrip():
    ciphertext = crypto.encrypt_secret("ghp_realtoken123")
    assert ciphertext != "ghp_realtoken123"
    assert crypto.decrypt_secret(ciphertext) == "ghp_realtoken123"


def test_raises_without_configured_key(monkeypatch):
    monkeypatch.setattr(crypto.settings, "encryption_key", "")
    with pytest.raises(RuntimeError):
        crypto.encrypt_secret("anything")
