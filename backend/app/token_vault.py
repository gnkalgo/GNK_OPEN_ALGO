from cryptography.fernet import Fernet, InvalidToken

from .config import Settings


class TokenVaultError(Exception):
    pass


def _fernet(config: Settings) -> Fernet:
    if not config.dhan_token_encryption_key:
        raise TokenVaultError("Dhan access-token encryption is not configured.")
    try:
        return Fernet(config.dhan_token_encryption_key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise TokenVaultError("Dhan access-token encryption key is invalid.") from exc


def encrypt_access_token(token: str, config: Settings) -> str:
    if not token:
        raise TokenVaultError("Dhan returned an empty access token.")
    return _fernet(config).encrypt(token.encode("utf-8")).decode("ascii")


def decrypt_access_token(ciphertext: str, config: Settings) -> str:
    try:
        return _fernet(config).decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeEncodeError, UnicodeDecodeError) as exc:
        raise TokenVaultError("Dhan access token could not be decrypted.") from exc
