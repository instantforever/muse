#!/usr/bin/env python3
"""Round-trip verification: compares hashes INSIDE this script and reports
only PASS/FAIL + sizes to stdout. Plaintext bytes/hashes never leave it."""
import hashlib, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
KEYS, GEN, ENC, DEC = ("work/keys", "work/gen", "work/enc", "work/dec")
ALGS = ["rsa2048", "rsa4096", "ed25519", "ed448", "mlkem768", "mlkem1024"]

def run(*args):
    r = subprocess.run([PY, os.path.join(HERE, "lenc.py"), *args],
                       capture_output=True, text=True, cwd=HERE)
    if r.returncode != 0:
        print("FAILED CMD:", args); print(r.stdout); print(r.stderr); sys.exit(1)
    return json.loads(r.stdout.strip().splitlines()[-1])

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()

os.makedirs("work", exist_ok=True)
os.makedirs(ENC, exist_ok=True); os.makedirs(DEC, exist_ok=True)
subprocess.run([PY, os.path.join(HERE, "generate_dummy.py"), GEN],
               check=True, cwd=HERE)
files = sorted(os.listdir(GEN))
results = []
for alg in ALGS:
    run("keygen", "--alg", alg, "--key-id", "t1", "--keys", KEYS)
    for name in files:
        src = os.path.join(GEN, name)
        enc = os.path.join(ENC, f"{name}.{alg}.lenc")
        rec = run("encrypt", "--alg", alg, "--infile", src, "--out", enc,
                  "--keys", KEYS)
        dst = os.path.join(DEC, f"{alg}-{name}")
        os.makedirs(DEC, exist_ok=True)
        out = run("decrypt", "--infile", enc, "--out", dst, "--keys", KEYS)
        ok = sha(src) == sha(dst) and out["ok"]
        results.append((alg, name, rec["in_bytes"], rec["out_bytes"],
                        rec["signed"], out["signature_verified"], ok))

fails = [r for r in results if not r[6]]
for alg, name, i, o, sgn, ver, ok in results:
    print(f"{alg:10s} {name:10s} {i:>8d} -> {o:>8d} bytes  "
          f"signed={sgn!s:5s} sig_verified={ver!s:5s} roundtrip={'PASS' if ok else 'FAIL'}")
print(f"\nTOTAL {len(results)} cases, {len(results)-len(fails)} PASS, {len(fails)} FAIL")

# --- key rotation: new active key, old files must still decrypt -------------
run("keygen", "--alg", "rsa2048", "--key-id", "t2", "--keys", KEYS)
src = os.path.join(GEN, "note.txt")
enc2 = os.path.join(ENC, "note-after-rotation.lenc")
rec2 = run("encrypt", "--alg", "rsa2048", "--infile", src, "--out", enc2, "--keys", KEYS)
dst2 = os.path.join(DEC, "note-after-rotation.txt")
out2 = run("decrypt", "--infile", enc2, "--out", dst2, "--keys", KEYS)
old_enc = os.path.join(ENC, "note.txt.rsa2048.lenc")
dst_old = os.path.join(DEC, "note-before-rotation.txt")
out_old = run("decrypt", "--infile", old_enc, "--out", dst_old, "--keys", KEYS)
rot_ok = (rec2["key_id"] == "t2" and sha(src) == sha(dst2)
          and sha(src) == sha(dst_old))
print(f"ROTATION   new key_id={rec2['key_id']}  new file decrypt="
      f"{'PASS' if sha(src)==sha(dst2) else 'FAIL'}  "
      f"old file (key t1) decrypt={'PASS' if sha(src)==sha(dst_old) else 'FAIL'}")
print("ROTATION", "PASS" if rot_ok else "FAIL")
sys.exit(1 if fails or not rot_ok else 0)
