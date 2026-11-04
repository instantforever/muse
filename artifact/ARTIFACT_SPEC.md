# ARTIFACT_SPEC — Encrypted Generation Pipeline (generic edition)

A specification for recreating the companion web artifact in your own
muse.ai (Muse) environment. Give this file (and the whole repository) to your
Muse and ask it to build an artifact following this spec.
See `../INSTALL_FOR_MUSE.md` for the step-by-step procedure.

This spec is intentionally free of any personal data: no names, no accounts,
no registered keys, no job history. A fresh build starts completely empty.

## Purpose

A control console for a “blind” generation-and-encryption pipeline:

- The user explicitly asks for a file to be generated **and encrypted**
  (e.g. in chat: “generate this and encrypt it”).
- The generated file (image / video / audio / text) is encrypted **without
  its contents being opened, rendered, or attached in the chat**, so the
  content never enters the AI's context and token consumption stays minimal.
- Only a metadata receipt is recorded: algorithm, key_id, input/output byte
  counts, SHA-256 of the ciphertext, signed flag, elapsed seconds.

## Architecture (two layers)

- **Artifact (this spec) = control tower**: key registry, generation-job
  intake, receipt ledger, and an in-browser encryption tool.
- **Python engine (`../lenc-pipeline/lenc.py`) = execution layer**: runs in
  the user's Muse workspace, receives generated files, and performs the
  actual encryption/decryption.
- Both layers share the **`.lenc` v1** container format, so a file encrypted
  by one layer can be decrypted by the other.

## Data model

Three tables, all starting empty. No sample or demo rows.

### keys
- `alg`: one of `rsa2048`, `rsa4096`, `ed25519`, `ed448`, `mlkem768`, `mlkem1024`
- `key_id`: user-chosen label
- `role`: `encrypt_pub` / `decrypt_priv` / `sign_pub` / `sign_priv`
- `key_text`: the key material (PEM text, or base64 text for ML-KEM)
- `fingerprint`: SHA-256 fingerprint of the key material
- `is_active`: whether this key is the active encryption key for its algorithm
- `note`: free text (optional)

Security invariants:
- List/read operations return **metadata and fingerprints only — never key
  material**. A dedicated single-key fetch exists solely for the in-app
  crypto tool, at the moment the user picks a registered key.
- Private keys are shown as fingerprints only, never rendered back.

### jobs
- `media_type`: `image` / `video` / `audio` / `text`
  Media types name the *kind* of content, never a file format. In
  particular `audio` is format-agnostic: it covers WAV, OGG, MP3, M4A,
  FLAC, AAC, Opus and any other audio file format. The same applies to
  the other types (any image / video / text format). The encryption
  engine treats every file as a binary stream, so extensions and
  container formats are irrelevant to the pipeline; UIs and docs must
  not present any single format (e.g. WAV) as “the” audio format.
- `instruction`: the generation instruction text
- `alg`: encryption algorithm to apply
- `backend`: generation backend identifier, free-form / extensible
  (examples: `muse-image`, `muse-video`, or an external generator).
  Backends are generic: a backend means “something that writes a file into
  the staging folder”. **No backend may hardcode a specific person,
  character, reference image, or appearance text.**
- `subject_profile` (optional, initially empty): if the user wants a
  recurring subject in generated media, *the user* registers their own
  profile — a reference-image path and/or a short appearance/context text —
  and jobs may attach it. It is user data, empty by default, and never
  pre-filled by the artifact.
- `status`: `queued` / `generated` / `encrypted` / `done` / `failed`
- `note`: free text (optional)

### receipts
- `job_id` (optional link), `alg`, `key_id`
- `in_bytes`, `out_bytes`, `ciphertext_sha256`, `signed`, `elapsed_seconds`
- File contents are never stored in a receipt.

## Actions (chat-facing API)

The artifact publishes actions so the user's Muse can drive it from chat:

- `registerKey`, `listKeys` (metadata only), `setActiveKey`, `deleteKey`
- `createJob`, `listJobs`, `updateJobStatus`, `deleteJob`
- `getSubjectProfile`, `saveSubjectProfile`, `deleteSubjectProfile`
  (the single optional subject profile described under `jobs` above)
- `recordReceipt`, `listReceipts`, `deleteReceipt`
- `getOverview` (active key per algorithm + job/receipt counts)
- `getKeyMaterial` (single key, for the in-app tool only)

## UI — four tabs (plus an optional fifth)

1. **Keys** — register a key by pasting PEM / base64 text, choosing alg,
   key_id and role; activate / rotate keys; generate a key pair in the
   browser and register the public half. Show a notice that in principle
   only public keys should be registered. Validate that the pasted key
   material matches the selected algorithm, and report registration
   success/failure explicitly with the fingerprint.
2. **Generation jobs** — create jobs (media type, instruction, alg,
   backend, optional subject profile), track status.
3. **Crypto tool** — encrypt / decrypt files entirely in the browser for
   all six algorithms, in the same `.lenc` v1 format as the Python engine,
   so the two are interoperable. If an algorithm cannot run in the
   browser, say so honestly and defer to the Python engine.
4. **Receipts** — the metadata-only ledger.

An optional fifth **Distribution** tab may present this package itself:
the repository link, the package layout, install steps, and the license
notes summarized from the top-level README.

## Encryption format (.lenc v1)

- Payload: random 256-bit DEK + AES-256-GCM, 1 MiB chunks.
- The selected algorithm wraps the DEK:
  - RSA: OAEP (SHA-256)
  - ML-KEM: KEM shared secret → HKDF → KEK wraps the DEK
  - Ed presets: X25519 / X448 ECDH wraps the DEK + mandatory Ed25519 /
    Ed448 signature (EdDSA itself cannot encrypt)
- Layout: one-line JSON header (magic, alg, key_id, KEM ciphertext, nonces;
  no plaintext information) + length-prefixed GCM chunks + optional
  fixed-length trailing signature.

## Non-goals / cautions

- The artifact itself does not generate media and does not see plaintext;
  generation and file handling happen in the user's own environment.
- Treat this as a working tool, not audited security software. See the
  license and third-party notices in the top-level README before using it
  to protect real secrets.
