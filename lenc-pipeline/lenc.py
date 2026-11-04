#!/usr/bin/env python3
"""
lenc.py - prototype: "generate -> encrypt without the assistant inspecting content"

Design notes (see DRAFT):
- All schemes are HYBRID: a random 256-bit data key (DEK) encrypts the file
  body with AES-256-GCM (chunked). The specified algorithm only wraps the DEK
  (and, for the Ed* presets, signs the package).
- RSA-2048 / RSA-4096 : RSA-OAEP(SHA-256) wraps the DEK directly.
- ML-KEM-768 / 1024   : Kyber KEM -> shared secret -> HKDF -> KEK wraps DEK.
  (FIPS 203 ML-KEM; prototype uses the pure-python kyber-py backend.)
- Ed25519 / Ed448     : EdDSA CANNOT encrypt. Preset therefore pairs
  X25519 / X448 ECDH (wraps the DEK) with a mandatory Ed25519 / Ed448
  signature over the package. That is the honest meaning of "Ed* specified".
- Keys are plain TEXT files (PEM for RSA/Ed/X; base64 text for ML-KEM).
  A manifest.json in the key dir selects the ACTIVE key per algorithm, so
  keys can be swapped later; every .lenc header carries its key_id.
- This tool never prints file content. Its receipt is JSON metadata only:
  sizes, algorithm, key_id, sha256 of the CIPHERTEXT.
"""
import argparse, base64, hashlib, json, os, struct, sys, time

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, ed25519, ed448, x25519, x448
from cryptography.hazmat.primitives.asymmetric.padding import OAEP, MGF1
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

CHUNK = 1 << 20  # 1 MiB
ALGS = ["rsa2048", "rsa4096", "ed25519", "ed448", "mlkem768", "mlkem1024"]


def b64e(b: bytes) -> str: return base64.b64encode(b).decode()
def b64d(s: str) -> bytes: return base64.b64decode(s)


def save_text(path, text):
    with open(path, "w") as f: f.write(text)
    os.chmod(path, 0o600 if "priv" in os.path.basename(path) else 0o644)

def pem_pub(key) -> str:
    return key.public_bytes(serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo).decode()

def pem_priv(key) -> str:
    return key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()).decode()

def load_pub(path):
    return serialization.load_pem_public_key(open(path, "rb").read())

def load_priv(path):
    return serialization.load_pem_private_key(open(path, "rb").read(), password=None)


def kem_mod(alg):
    from kyber_py.ml_kem import ML_KEM_768, ML_KEM_1024
    return ML_KEM_768 if alg == "mlkem768" else ML_KEM_1024


# ---------------- key generation (TEST keys / user-side key ceremony) -------
def cmd_keygen(a):
    os.makedirs(a.keys, exist_ok=True)
    kid = a.key_id
    ent = {"key_id": kid, "alg": a.alg, "files": {}}
    if a.alg in ("rsa2048", "rsa4096"):
        bits = 2048 if a.alg == "rsa2048" else 4096
        k = rsa.generate_private_key(public_exponent=65537, key_size=bits)
        ent["files"] = {"pub": f"{a.alg}-{kid}.pub.pem", "priv": f"{a.alg}-{kid}.priv.pem"}
        save_text(os.path.join(a.keys, ent["files"]["pub"]), pem_pub(k.public_key()))
        save_text(os.path.join(a.keys, ent["files"]["priv"]), pem_priv(k))
    elif a.alg in ("mlkem768", "mlkem1024"):
        ek, dk = kem_mod(a.alg).keygen()
        ent["files"] = {"pub": f"{a.alg}-{kid}.pub.txt", "priv": f"{a.alg}-{kid}.priv.txt"}
        hdr = "ML-KEM ENCAPSULATION KEY" if a.alg == "mlkem768" else "ML-KEM ENCAPSULATION KEY"
        save_text(os.path.join(a.keys, ent["files"]["pub"]),
                  f"# {a.alg} {hdr} (base64)\n" + b64e(ek) + "\n")
        save_text(os.path.join(a.keys, ent["files"]["priv"]),
                  f"# {a.alg} ML-KEM DECAPSULATION KEY (base64) - SECRET\n" + b64e(dk) + "\n")
    elif a.alg in ("ed25519", "ed448"):
        xk = x25519.X25519PrivateKey.generate() if a.alg == "ed25519" else x448.X448PrivateKey.generate()
        sk = ed25519.Ed25519PrivateKey.generate() if a.alg == "ed25519" else ed448.Ed448PrivateKey.generate()
        ent["files"] = {
            "pub": f"{a.alg}-{kid}.x.pub.pem", "priv": f"{a.alg}-{kid}.x.priv.pem",
            "sign_pub": f"{a.alg}-{kid}.sign.pub.pem", "sign_priv": f"{a.alg}-{kid}.sign.priv.pem"}
        save_text(os.path.join(a.keys, ent["files"]["pub"]), pem_pub(xk.public_key()))
        save_text(os.path.join(a.keys, ent["files"]["priv"]), pem_priv(xk))
        save_text(os.path.join(a.keys, ent["files"]["sign_pub"]), pem_pub(sk.public_key()))
        save_text(os.path.join(a.keys, ent["files"]["sign_priv"]), pem_priv(sk))
    mpath = os.path.join(a.keys, "manifest.json")
    man = json.load(open(mpath)) if os.path.exists(mpath) else {}
    slot = man.setdefault(a.alg, {"active": None, "keys": {}})
    slot["keys"][kid] = ent   # old keys are KEPT, so old files still decrypt
    slot["active"] = kid      # ... while the new key becomes the active one
    json.dump(man, open(mpath, "w"), indent=2)
    print(json.dumps({"ok": True, "action": "keygen", "alg": a.alg, "key_id": kid,
                      "active": True}))


def active_entry(keys_dir, alg):
    man = json.load(open(os.path.join(keys_dir, "manifest.json")))
    if alg not in man: sys.exit(f"no active key for {alg}")
    slot = man[alg]
    return slot["keys"][slot["active"]]


def read_mlkem(path):
    lines = [l.strip() for l in open(path) if l.strip() and not l.startswith("#")]
    return b64d("".join(lines))


# ---------------- encryption -------------------------------------------------
def wrap_dek(alg, ent, keys_dir, dek):
    """Return header kem fields."""
    if alg in ("rsa2048", "rsa4096"):
        pub = load_pub(os.path.join(keys_dir, ent["files"]["pub"]))
        ct = pub.encrypt(dek, OAEP(mgf=MGF1(hashes.SHA256()),
                                   algorithm=hashes.SHA256(), label=None))
        return {"kem_ct": b64e(ct)}
    if alg in ("mlkem768", "mlkem1024"):
        ek = read_mlkem(os.path.join(keys_dir, ent["files"]["pub"]))
        ss, ct = kem_mod(alg).encaps(ek)
        kek = HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                   info=b"lenc-kek").derive(ss)
        wn = os.urandom(12)
        return {"kem_ct": b64e(ct), "wrap_nonce": b64e(wn),
                "wrapped_dek": b64e(AESGCM(kek).encrypt(wn, dek, None))}
    # ed25519 / ed448 via X25519 / X448 ephemeral ECDH
    pub = load_pub(os.path.join(keys_dir, ent["files"]["pub"]))
    eph = x25519.X25519PrivateKey.generate() if alg == "ed25519" else x448.X448PrivateKey.generate()
    ss = eph.exchange(pub)
    kek = HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
               info=b"lenc-kek").derive(ss)
    wn = os.urandom(12)
    return {"kem_ct": b64e(eph.public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw)),
            "wrap_nonce": b64e(wn),
            "wrapped_dek": b64e(AESGCM(kek).encrypt(wn, dek, None))}


def unwrap_dek(alg, ent, keys_dir, hdr):
    if alg in ("rsa2048", "rsa4096"):
        priv = load_priv(os.path.join(keys_dir, ent["files"]["priv"]))
        return priv.decrypt(b64d(hdr["kem_ct"]),
                            OAEP(mgf=MGF1(hashes.SHA256()),
                                 algorithm=hashes.SHA256(), label=None))
    if alg in ("mlkem768", "mlkem1024"):
        dk = read_mlkem(os.path.join(keys_dir, ent["files"]["priv"]))
        ss = kem_mod(alg).decaps(dk, b64d(hdr["kem_ct"]))
    else:
        priv = load_priv(os.path.join(keys_dir, ent["files"]["priv"]))
        eph_cls = x25519.X25519PublicKey if alg == "ed25519" else x448.X448PublicKey
        ss = priv.exchange(eph_cls.from_public_bytes(b64d(hdr["kem_ct"])))
    kek = HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
               info=b"lenc-kek").derive(ss)
    return AESGCM(kek).decrypt(b64d(hdr["wrap_nonce"]), b64d(hdr["wrapped_dek"]), None)


def cmd_encrypt(a):
    t0 = time.time()
    ent = active_entry(a.keys, a.alg)
    dek = AESGCM.generate_key(bit_length=256)
    size = os.path.getsize(a.infile)
    n_chunks = (size + CHUNK - 1) // CHUNK if size else 0
    body_len = sum(4 + min(CHUNK, size - i * CHUNK) + 16 for i in range(n_chunks))
    hdr = {"v": 1, "magic": "LENC1", "alg": a.alg, "key_id": ent["key_id"],
           "chunk": CHUNK, "plain_size": size, "body_len": body_len,
           "nonce_base": b64e(os.urandom(8))}
    hdr.update(wrap_dek(a.alg, ent, a.keys, dek))
    hdr["sign_alg"] = a.alg if a.alg in ("ed25519", "ed448") else None
    hdr_bytes = (json.dumps(hdr, separators=(",", ":")) + "\n").encode()
    aes = AESGCM(dek)
    body_hash = hashlib.sha256()
    body_len = 0
    with open(a.infile, "rb") as fin, open(a.out, "wb") as fout:
        fout.write(hdr_bytes)
        counter = 0
        while True:
            chunk = fin.read(CHUNK)
            if not chunk: break
            nonce = b64d(hdr["nonce_base"]) + struct.pack(">I", counter)
            ct = aes.encrypt(nonce, chunk, None)
            rec = struct.pack(">I", len(ct)) + ct
            body_hash.update(rec); body_len += len(rec)
            fout.write(rec); counter += 1
        if hdr["sign_alg"]:
            # trailer = raw signature bytes, fixed length per algorithm
            # (Ed25519: 64, Ed448: 114), appended right after the body
            sk = load_priv(os.path.join(a.keys, ent["files"]["sign_priv"]))
            fout.write(sk.sign(hdr_bytes + body_hash.digest()))
    out_size = os.path.getsize(a.out)
    ct_hash = hashlib.sha256(open(a.out, "rb").read()).hexdigest()
    print(json.dumps({"ok": True, "action": "encrypt", "alg": a.alg,
                      "key_id": ent["key_id"], "in_bytes": size,
                      "out_bytes": out_size, "ciphertext_sha256": ct_hash,
                      "signed": bool(hdr["sign_alg"]),
                      "seconds": round(time.time() - t0, 3)}))


def cmd_decrypt(a):
    t0 = time.time()
    raw = open(a.infile, "rb")
    hdr = json.loads(raw.readline())
    ent = None
    man = json.load(open(os.path.join(a.keys, "manifest.json")))
    # decryption looks the key up by the header's key_id, not just "active",
    # so files encrypted before a key rotation still decrypt.
    for slot in man.values():
        for e in slot.get("keys", {}).values():
            if e["key_id"] == hdr["key_id"] and e["alg"] == hdr["alg"]: ent = e
    if ent is None: sys.exit("key_id from header not found in key dir")
    rest = raw.read()
    sig_ok = False
    if hdr["sign_alg"]:
        sig_len = 64 if hdr["sign_alg"] == "ed25519" else 114
        sig, body = rest[-sig_len:], rest[:-sig_len]
        assert len(body) == hdr["body_len"], "body length mismatch"
        pub = load_pub(os.path.join(a.keys, ent["files"]["sign_pub"]))
        pub.verify(sig, (json.dumps(hdr, separators=(",", ":")) + "\n").encode()
                   + hashlib.sha256(body).digest())
        sig_ok = True
    else:
        body = rest
    dek = unwrap_dek(hdr["alg"], ent, a.keys, hdr)
    aes = AESGCM(dek)
    plain_hash = hashlib.sha256()
    written = 0
    with open(a.out, "wb") as fout:
        off, counter = 0, 0
        while off < len(body):
            (ln,) = struct.unpack(">I", body[off:off + 4]); off += 4
            ct = body[off:off + ln]; off += ln
            nonce = b64d(hdr["nonce_base"]) + struct.pack(">I", counter)
            pt = aes.decrypt(nonce, ct, None)
            plain_hash.update(pt); written += len(pt)
            fout.write(pt); counter += 1
    ok = written == hdr["plain_size"]
    print(json.dumps({"ok": ok, "action": "decrypt", "alg": hdr["alg"],
                      "key_id": hdr["key_id"], "signature_verified": sig_ok,
                      "out_bytes": written,
                      "plaintext_sha256_internal": plain_hash.hexdigest(),
                      "seconds": round(time.time() - t0, 3)}))


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(required=True)
    k = sub.add_parser("keygen"); k.add_argument("--alg", choices=ALGS, required=True)
    k.add_argument("--key-id", required=True); k.add_argument("--keys", default="keys")
    k.set_defaults(fn=cmd_keygen)
    e = sub.add_parser("encrypt"); e.add_argument("--alg", choices=ALGS, required=True)
    e.add_argument("--infile", required=True); e.add_argument("--out", required=True)
    e.add_argument("--keys", default="keys"); e.set_defaults(fn=cmd_encrypt)
    d = sub.add_parser("decrypt"); d.add_argument("--infile", required=True)
    d.add_argument("--out", required=True); d.add_argument("--keys", default="keys")
    d.set_defaults(fn=cmd_decrypt)
    a = p.parse_args(); a.fn(a)


if __name__ == "__main__":
    main()
