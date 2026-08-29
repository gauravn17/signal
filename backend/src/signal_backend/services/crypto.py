from cryptography.fernet import Fernet

from signal_backend.config import settings


def _cipher() -> Fernet:
    if not settings.encryption_key:
        raise RuntimeError(
            "SIGNAL_ENCRYPTION_KEY is not configured — required to store an organization's API keys."
        )
    return Fernet(settings.encryption_key.encode())


def encrypt_secret(plaintext: str) -> str:
    return _cipher().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    return _cipher().decrypt(ciphertext.encode()).decode()
