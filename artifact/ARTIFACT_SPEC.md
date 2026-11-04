# ARTIFACT_SPEC — Sealed Generation Pipeline (generic edition)

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
- `backend`: one of the built-in backends `muse-image` / `muse-video`
  (the generators built into the user's own Muse environment), or
  `external`. A job that uses a user-registered generation AI (see
  `backends` below) is recorded as `backend = external` together with
  `backend_name` = the registered name, so the name the user chose is
  preserved on the job and shown in the job list.
  Backends are generic: a backend means “something that writes a file into
  the staging folder”. **No backend may hardcode a specific person,
  character, reference image, or appearance text.**

### backends (user-registered generation AIs)
Starts empty. This registry is how a user makes *their own* generation
AIs (image / music / video / text services or helper programs) selectable
as job backends — without it, only the built-ins and a generic
`external` are available.

- `name`: display name of the generation AI, chosen by the user
  (e.g. the service or helper they actually use)
- `media_types`: which media kinds it can produce
  (`image` / `video` / `audio` / `text`; empty = any)
- `note`: how the user's Muse reaches it in the user's own environment
  (a connected tool / connector, an API, a local helper program, plus the
  staging-folder contract). Free text for the executing agent.
  **Never store credentials or API keys here.**

What registering a backend does — and does not do:

- It adds the name to the job-creation form's backend choices, filtered
  to backends whose media types match the job's media type.
- Jobs created with it record the name, and the executing agent uses the
  name and note to generate with that AI.
- It does **not** connect or call the service by itself: the artifact
  never executes a generator. The generation AI must already be usable
  in the user's Muse environment (connected tool, API access, or a
  helper program) — registration only makes it selectable and recorded.
- Deleting a registration removes it from future choices only; jobs
  already created keep the recorded name as text.
- The built-in generic `external` item itself can also be removed:
  a persisted preference (`external_hidden`, default false) hides it from
  the job-creation choices and makes the server reject unnamed external
  jobs, while jobs using a registered backend name keep working. The
  preference is reversible at any time and does not affect jobs already
  created.
- `subject_profile` (optional, initially empty): if the user wants a
  recurring subject in generated media, *the user* registers their own
  profile — a reference-image path and/or a short appearance/context text —
  and jobs may attach it. It is user data, empty by default, and never
  pre-filled by the artifact.
- `status`: `queued` / `generated` / `encrypted` / `done` / `failed`
- `output_format`: `lenc` (default) or `gpg` — the encryption container
  for this job (see “Output formats” below)
- execution request: a queued job can carry an execution request
  (requested timestamp) placed from the UI's “request execution” button.
  Requesting hands the job to the user's AI companion as a background
  task; a job that already has a request cannot be requested twice
- `note`: free text (optional)

### receipts
- `job_id` (optional link), `alg`, `key_id`, `output_format`
  (`lenc` / `gpg`)
- `in_bytes`, `out_bytes`, `ciphertext_sha256`, `signed`, `elapsed_seconds`
- File contents are never stored in a receipt.

## Actions (chat-facing API)

The artifact publishes actions so the user's Muse can drive it from chat:

- `registerKey`, `listKeys` (metadata only), `setActiveKey`, `deleteKey`
- `registerBackend`, `listBackends`, `deleteBackend`
  (the user-registered generation AIs described under `jobs` above;
  `createJob` takes `backend_name` together with `backend = external`
  to use one of them; `listBackends` also returns `external_hidden`)
- `setExternalBackendHidden` (remove / restore the built-in `external`
  item, as described under `jobs` above)
- `createJob`, `listJobs`, `updateJobStatus`, `deleteJob`
  (`createJob` also takes `output_format`)
- `requestJobExecution` (the UI button's action: hands one queued job
  to the user's AI companion as a background task), `reportJobExecution`
  (the executing agent reports completion — job done + receipt in one
  step — or failure with a reason)
- `getSubjectProfile`, `saveSubjectProfile`, `deleteSubjectProfile`
  (the single optional subject profile described under `jobs` above)
- `recordReceipt`, `listReceipts`, `deleteReceipt`
- `getOverview` (active key per algorithm + job/receipt counts)
- `getKeyMaterial` (single key, for the in-app tool only)

## UI — four tabs (plus an optional fifth)

1. **Keys** — register a key by pasting PEM / base64 text, choosing alg,
   key_id and role; activate / rotate keys; generate a key pair in the
   browser and register the public half. For `gpg` output, an OpenPGP
   public key block may be registered as the destination key under the
   matching algorithm label. Show a notice that in principle
   only public keys should be registered. Validate that the pasted key
   material matches the selected algorithm, and report registration
   success/failure explicitly with the fingerprint.
2. **Generation jobs** — create jobs (media type, instruction, alg,
   backend, output format, optional subject profile), track status.
   Each queued job offers a “request execution” button that hands the
   job to the user's AI companion. Includes a
   “register your own generation AI as a backend” section (name, media
   types, how-to-reach-it note) and visible explanations of how to add a
   backend, what happens when one is added (it becomes a job choice and
   its name is recorded on jobs), and what registration does not do
   (it neither connects nor calls the service by itself, and no
   credentials are stored). The built-in `external` item is listed in
   the same section and can be removed there (with confirmation) and
   restored; see the `external_hidden` preference under `jobs`.
3. **Crypto tool** — encrypt / decrypt files entirely in the browser for
   all six algorithms, in the same `.lenc` v1 format as the Python engine,
   so the two are interoperable. It covers the `lenc` format only; `gpg`
   output is produced by the executing agent. If an algorithm cannot run in the
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

## Output formats

- `lenc` — the format above; produced and consumed by both the in-browser
  tool and the Python engine.
- `gpg` — a standard OpenPGP message encrypted to the recipient key
  registered for the job (an OpenPGP public key block, e.g. RSA or
  Ed25519/X25519, Ed448/X448 keys), decryptable with ordinary GPG tools
  and the user's PGP private key. Production happens on the executing
  side (the companion / the user's GPG); the Python engine is
  `lenc`-only. The chosen format is recorded on both the job and its
  receipt.

## Non-goals / cautions

- The artifact itself does not generate media and does not see plaintext;
  generation and file handling happen in the user's own environment.
- Treat this as a working tool, not audited security software. See the
  license and third-party notices in the top-level README before using it
  to protect real secrets.
