"""
YouTube ke naye (comment/playlist ijazat wale) refresh tokens - repo mein ENCRYPTED rakhe jaate hain
(yt_tokens/<account>.enc), taake GitHub secrets mein haath se paste na karna pare.
Key us channel ke CLIENT_SECRET se banti hai: secret ke baghair file bekaar hai (aur refresh token
waise bhi client secret ke baghair kaam nahi karta). Sirf Python standard library.
"""
import os
import hmac
import base64
import hashlib

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yt_tokens")


def _keys(secret):
    k = hashlib.sha256(("yt-token-v1:" + secret).encode()).digest()
    return hashlib.sha256(k + b"enc").digest(), hashlib.sha256(k + b"mac").digest()


def _stream(key, nonce, n):
    out, i = b"", 0
    while len(out) < n:
        out += hmac.new(key, nonce + i.to_bytes(8, "big"), hashlib.sha256).digest()
        i += 1
    return out[:n]


def encrypt(text, secret):
    ek, mk = _keys(secret)
    nonce = os.urandom(16)
    data = text.encode()
    ct = bytes(a ^ b for a, b in zip(data, _stream(ek, nonce, len(data))))
    tag = hmac.new(mk, nonce + ct, hashlib.sha256).digest()
    return base64.b64encode(nonce + tag + ct).decode()


def decrypt(blob, secret):
    ek, mk = _keys(secret)
    raw = base64.b64decode(blob)
    nonce, tag, ct = raw[:16], raw[16:48], raw[48:]
    if not hmac.compare_digest(tag, hmac.new(mk, nonce + ct, hashlib.sha256).digest()):
        raise ValueError("token file is client secret se nahi khulti")
    return bytes(a ^ b for a, b in zip(ct, _stream(ek, nonce, len(ct)))).decode()


def get(account, secret):
    """Repo mein naya token ho to woh, warna None (tab purana secret wala token chalega)."""
    path = os.path.join(DIR, f"{account}.enc")
    if not (secret and os.path.exists(path)):
        return None
    try:
        return decrypt(open(path).read().strip(), secret)
    except Exception as e:
        print(f"[yt_tokens] {account}: {e}", flush=True)
        return None


def save(account, token, secret):
    os.makedirs(DIR, exist_ok=True)
    with open(os.path.join(DIR, f"{account}.enc"), "w") as f:
        f.write(encrypt(token, secret) + "\n")
