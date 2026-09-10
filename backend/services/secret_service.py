import os
import base64
import hashlib
import logging
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

def _get_fernet() -> Fernet:
    secret = os.getenv("HADIL_JWT_SECRET", "hadil-dev-secret-key-change-in-production-12345")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode('utf-8')).digest())
    return Fernet(key)

def encrypt_secret(raw_secret: str) -> str:
    """
    Encrypts sensitive string (API Key) using Fernet key derived from HADIL_JWT_SECRET.
    """
    if not raw_secret:
        return ""
    try:
        f = _get_fernet()
        return f.encrypt(raw_secret.encode('utf-8')).decode('utf-8')
    except Exception as e:
        logger.error(f"Error encrypting secret: {e}")
        return ""

def decrypt_secret(encrypted_secret: str) -> str:
    """
    Decrypts encrypted secret back to raw plaintext for internal API calls.
    """
    if not encrypted_secret:
        return ""
    try:
        f = _get_fernet()
        return f.decrypt(encrypted_secret.encode('utf-8')).decode('utf-8')
    except Exception as e:
        logger.error(f"Error decrypting secret: {e}")
        return ""
