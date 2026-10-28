"""
Token encryption for third-party OAuth credentials.

Access tokens and refresh tokens are encrypted with Fernet (AES-128-CBC +
HMAC-SHA256) before being written to the database.  The encryption key lives
in the environment — never in the database or source code.

Key rotation:
  Generate a new key with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  Set INTEGRATION_ENCRYPTION_KEY in your environment / secrets manager.
"""

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.integrations.exceptions import IntegrationError


def _fernet() -> Fernet:
    key = settings.INTEGRATION_ENCRYPTION_KEY
    if not key:
        raise IntegrationError(
            "INTEGRATION_ENCRYPTION_KEY is not set. Cannot encrypt or decrypt integration tokens."
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_token(plaintext: str) -> str:
    """Encrypt a token string. Returns a URL-safe base64 ciphertext string."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a token string. Raises IntegrationError if the key is wrong or data is corrupt."""
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise IntegrationError(
            "Failed to decrypt integration token. The encryption key may have been rotated."
        ) from exc
