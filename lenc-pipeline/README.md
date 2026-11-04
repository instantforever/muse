# lenc-pipeline — execution engine for the Encrypted Generation Pipeline

The command-line execution engine of this project. It encrypts files produced by a
generator (image / video / audio / text) **without opening or displaying their
contents**, and returns only a metadata receipt.

Design details: see `../artifact/ARTIFACT_SPEC.md`. Top-level overview, install
guide and license notes: see `../README.md`.

## How it works

1. A generator writes a file into a staging folder.
2. `lenc.py` reads the file as a binary stream and encrypts it into a `.lenc` container.
3. The operator (a human or an AI assistant) receives only a receipt JSON:
   `{alg, key_id, in_bytes, out_bytes, ciphertext_sha256, signed, seconds}`.
   The plaintext never enters a chat context, which keeps token usage minimal
   when an AI assistant drives the pipeline.

## Supported algorithms (all hybrid encryption)

The payload is always encrypted with a random 256-bit DEK + AES-256-GCM
(1 MiB chunks, so large video files stream at constant memory).
The selected algorithm wraps the DEK (and signs, for the Ed presets):

| Selection | Implementation |
|---|---|
| `rsa2048` / `rsa4096` | RSA-OAEP (SHA-256) wraps the DEK |
| `mlkem768` / `mlkem1024` | ML-KEM (FIPS 203, “Kyber”): KEM shared secret → HKDF → KEK wraps the DEK |
| `ed25519` / `ed448` | EdDSA is signature-only and cannot encrypt. This preset wraps the DEK with X25519 / X448 ECDH and attaches a mandatory Ed25519 / Ed448 signature |

Container format `.lenc` v1: first line is a JSON header (magic, alg, key_id,
KEM ciphertext, nonces — no plaintext information), followed by length-prefixed
GCM chunks, followed by a fixed-length signature when signing applies.

## Keys

- Text files: PEM for RSA / Ed / X keys; base64 text for ML-KEM (no standard PEM exists).
- **For encryption you only need to hand the operator a public key.**
  Keep decryption private keys on your own side. The exception is the Ed
  signing key, which is a separate secret from the decryption key — store it carefully.
- A `manifest.json` in the keys folder records the active `key_id` per algorithm.
  Rotation = generate/register a new key and activate it. The `key_id` is stored
  in each file header, so files made before a rotation stay decryptable with
  their corresponding private key.

## Usage

```bash
./setup.sh   # creates .venv in this folder and installs dependencies

# generate a test key and activate it
.venv/bin/python lenc.py keygen --alg rsa2048 --key-id mykey1 --keys keys

# encrypt (prints only the receipt JSON)
.venv/bin/python lenc.py encrypt --alg rsa2048 --infile <generated-file> --out <output.lenc> --keys keys

# decrypt (recipient side; the key is chosen automatically from the header key_id)
.venv/bin/python lenc.py decrypt --infile <file.lenc> --out <restored-file> --keys keys
```

## Verification

```bash
.venv/bin/python run_tests.py
```

Runs round-trip checks for 6 algorithms × 4 sample file types
(txt / png / wav / mp4), tamper rejection (one flipped ciphertext byte),
and key rotation.
It prints only PASS/FAIL and sizes — never plaintext or plaintext hashes.

The four samples are representatives only. The engine is format-agnostic:
it encrypts any file as a binary stream. In particular, “audio” is not
limited to WAV — OGG, MP3, M4A, FLAC, AAC, Opus and any other audio
format work exactly the same way, as do other image, video and text
formats.

## Production warnings

- The ML-KEM backend is the pure-Python `kyber-py` package. Upstream describes
  it as an **educational implementation that should not be used for real
  cryptographic applications**. Replace it with a maintained, audited
  implementation (e.g. liboqs bindings) before protecting real secrets.
- This engine covers only the “generate → encrypt” encryption step. Connecting
  a specific generator backend is the operator's job — anything that writes a
  file into the staging folder can be plugged in.
- Never store private key files in plaintext on a shared machine or in a
  repository. Hand over public keys only, in principle.
