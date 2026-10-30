"""
crypto.py – Encryption for non-synthetic outputs.

For modes other than 'synthetic', output files are encrypted at rest
using AES-256-GCM (authenticated encryption).

The key is read from OUTPUT_ENCRYPTION_KEY env var (64 hex chars = 32 bytes).

Production note: this is a simple reference implementation.
A production setup would use:
  - Hardware security module (HSM) or cloud KMS for key management
  - Key rotation policy
  - Separate keys per patient or per day
  - Audit log of every key use
  See docs/DATA_PROTECTION.md for details.
"""

from __future__ import annotations

import os
import struct
from pathlib import Path

# cryptography package (pip install cryptography)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _get_key() -> bytes:
    hex_key = os.environ.get("OUTPUT_ENCRYPTION_KEY", "")
    if not hex_key or len(hex_key) != 64:
        raise EnvironmentError(
            "OUTPUT_ENCRYPTION_KEY must be 64 hex characters (32 bytes / 256 bits). "
            "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    return bytes.fromhex(hex_key)


def encrypt_file(path: Path, plaintext: bytes) -> None:
    """Write plaintext as AES-256-GCM encrypted file."""
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce (recommended for GCM)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    # File format: 4-byte magic | 12-byte nonce | ciphertext+tag
    magic = b"IPSC"
    with path.open("wb") as f:
        f.write(magic)
        f.write(nonce)
        f.write(ciphertext)


def decrypt_file(path: Path) -> bytes:
    """Read and decrypt an AES-256-GCM encrypted file."""
    key = _get_key()
    aesgcm = AESGCM(key)
    with path.open("rb") as f:
        magic = f.read(4)
        if magic != b"IPSC":
            raise ValueError(f"Not an encrypted IPS file: {path}")
        nonce = f.read(12)
        ciphertext = f.read()
    return aesgcm.decrypt(nonce, ciphertext, None)


def write_output(
    path: Path,
    content: str | bytes,
    mode: str,
    encoding: str = "utf-8",
) -> None:
    """
    Write content to path.
    For non-synthetic modes, encrypt at rest.
    """
    if isinstance(content, str):
        content_bytes = content.encode(encoding)
    else:
        content_bytes = content

    if mode == "synthetic":
        path.write_bytes(content_bytes)
    else:
        encrypted_path = path.with_suffix(path.suffix + ".enc")
        encrypt_file(encrypted_path, content_bytes)
