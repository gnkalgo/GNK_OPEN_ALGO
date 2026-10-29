from types import SimpleNamespace

import pytest

from app.token_vault import (
    TokenVaultError,
    decrypt_access_token,
    encrypt_access_token,
)

FERNET_KEY = "MTIzNDU2Nzg5MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTI="


def test_access_token_encryption_round_trips_without_exposing_plaintext():
    config = SimpleNamespace(dhan_token_encryption_key=FERNET_KEY)
    token = "secret-access-token"

    ciphertext = encrypt_access_token(token, config)

    assert ciphertext != token
    assert token not in ciphertext
    assert decrypt_access_token(ciphertext, config) == token


def test_access_token_encryption_requires_a_valid_key():
    for key in ("", "invalid-key"):
        with pytest.raises(TokenVaultError):
            encrypt_access_token("secret-access-token", SimpleNamespace(dhan_token_encryption_key=key))


def test_access_token_decryption_rejects_tampered_ciphertext():
    config = SimpleNamespace(dhan_token_encryption_key=FERNET_KEY)
    ciphertext = encrypt_access_token("secret-access-token", config)

    with pytest.raises(TokenVaultError):
        decrypt_access_token(ciphertext[:-1] + ("A" if ciphertext[-1] != "A" else "B"), config)
