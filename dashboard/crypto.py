"""AES-256-GCM with a PBKDF2 key; format matches WebCrypto decryption in site/index.html."""
import base64, json, os
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ITERATIONS = 600_000


def _key(passphrase, salt):
    return PBKDF2HMAC(hashes.SHA256(), 32, salt, ITERATIONS).derive(passphrase.encode())


def encrypt(obj, passphrase):
    salt, iv = os.urandom(16), os.urandom(12)
    ct = AESGCM(_key(passphrase, salt)).encrypt(iv, json.dumps(obj).encode(), None)  # tag appended, as WebCrypto expects
    b = lambda x: base64.b64encode(x).decode()
    return {"salt": b(salt), "iv": b(iv), "ct": b(ct)}


def decrypt(blob, passphrase):
    d = {k: base64.b64decode(v) for k, v in blob.items()}
    return json.loads(AESGCM(_key(passphrase, d["salt"])).decrypt(d["iv"], d["ct"], None))
