"""
Encryption utilities for RPC Authentication System.
Supports:
  - Symmetric encryption  : AES-256-CBC (via cryptography library)
  - Asymmetric encryption : RSA-2048     (via cryptography library)
"""

import os
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as sym_padding
from cryptography.hazmat.primitives.asymmetric import rsa, padding as asym_padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend


# ──────────────────────────────────────────────
#  SYMMETRIC  (AES-256-CBC)
# ──────────────────────────────────────────────

class AESCipher:
    """AES-256-CBC symmetric encryption / decryption."""

    KEY_SIZE   = 32   # 256 bits
    BLOCK_SIZE = 16   # 128 bits

    @staticmethod
    def generate_key() -> bytes:
        """Generate a cryptographically-random 256-bit key."""
        return os.urandom(AESCipher.KEY_SIZE)

    @staticmethod
    def encrypt(key: bytes, plaintext: str) -> str:
        """Encrypt *plaintext* string → base64-encoded  IV||ciphertext."""
        iv   = os.urandom(AESCipher.BLOCK_SIZE)
        padder = sym_padding.PKCS7(128).padder()
        padded = padder.update(plaintext.encode()) + padder.finalize()
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        enc    = cipher.encryptor()
        ct     = enc.update(padded) + enc.finalize()
        return base64.b64encode(iv + ct).decode()

    @staticmethod
    def decrypt(key: bytes, token: str) -> str:
        """Decrypt base64-encoded IV||ciphertext → plaintext string."""
        raw    = base64.b64decode(token)
        iv, ct = raw[:AESCipher.BLOCK_SIZE], raw[AESCipher.BLOCK_SIZE:]
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        dec    = cipher.decryptor()
        padded = dec.update(ct) + dec.finalize()
        unpadder = sym_padding.PKCS7(128).unpadder()
        return (unpadder.update(padded) + unpadder.finalize()).decode()

    @staticmethod
    def key_to_hex(key: bytes) -> str:
        return key.hex()

    @staticmethod
    def key_from_hex(hex_str: str) -> bytes:
        return bytes.fromhex(hex_str)


# ──────────────────────────────────────────────
#  ASYMMETRIC  (RSA-2048)
# ──────────────────────────────────────────────

class RSACipher:
    """RSA-2048 asymmetric encryption / decryption."""

    @staticmethod
    def generate_keypair():
        """Return (private_key, public_key) RSA objects."""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        return private_key, private_key.public_key()

    @staticmethod
    def encrypt(public_key, plaintext: str) -> str:
        """Encrypt with public key → base64 ciphertext."""
        ct = public_key.encrypt(
            plaintext.encode(),
            asym_padding.OAEP(
                mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return base64.b64encode(ct).decode()

    @staticmethod
    def decrypt(private_key, token: str) -> str:
        """Decrypt base64 ciphertext with private key → plaintext."""
        ct = base64.b64decode(token)
        return private_key.decrypt(
            ct,
            asym_padding.OAEP(
                mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        ).decode()

    @staticmethod
    def serialize_public_key(public_key) -> str:
        """PEM string for the public key."""
        return public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()

    @staticmethod
    def load_public_key(pem: str):
        return serialization.load_pem_public_key(pem.encode(), backend=default_backend())
