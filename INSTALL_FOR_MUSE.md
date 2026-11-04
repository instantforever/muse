# Installing this in your own muse.ai environment

This repository is a distribution package for people who use
[muse.ai](https://muse.ai). It contains everything your own Muse needs to
recreate the **Sealed Generation Pipeline** in *your* environment:
nothing here connects back to the author's environment, accounts, or data.

## Steps

1. **Download this repository** from GitHub
   (green **Code** button → **Download ZIP**), or clone it.
2. **Hand it to your Muse.** In your Muse chat, attach / upload the ZIP
   (or the extracted folder) and say, for example:

   > This is the Sealed Generation Pipeline distribution package.
   > Please read `INSTALL_FOR_MUSE.md` and `artifact/ARTIFACT_SPEC.md`,
   > then build the artifact exactly as the spec describes — empty, with
   > no sample data — and install the Python engine from `lenc-pipeline/`
   > into my workspace.

3. **Your Muse builds two things:**
   - a web artifact (the control console) following
     `artifact/ARTIFACT_SPEC.md` — tabs: Keys / Generation jobs /
     Crypto tool / Receipts / Distribution, starting with an empty database;
   - the Python engine in your workspace (`lenc-pipeline/lenc.py`),
     set up with `./setup.sh` and verified with
     `.venv/bin/python run_tests.py` (expected: 24/24 PASS + rotation PASS).
4. **Register your own key.** In the artifact's Keys tab, generate a key
   pair in the browser or register a public key you made yourself.
   In principle, give your Muse **public keys only**; keep private
   (decryption) keys on your own side.
5. **Use it from chat — or from the artifact.** Ask your Muse things like
   “generate an image of … and encrypt it with RSA-2048”.
   Your Muse creates a job in the artifact, generates the file, encrypts
   it with the Python engine without opening it, records a
   metadata-only receipt, and delivers the `.lenc` file to you.
   You decrypt it locally with your private key:

   ```bash
   .venv/bin/python lenc.py decrypt --infile <file.lenc> --out <restored-file> --keys keys
   ```

   Alternatively, register a job yourself in the Generation jobs tab and
   press its “request execution” button: your Muse companion picks it up
   as a background task and runs the same flow. Each job also chooses its
   output format — `.lenc`, or `.gpg` (a standard OpenPGP message to a
   registered OpenPGP public key, for people who prefer GPG tooling).

## Notes

- Each Muse environment is separate: your artifact, your keys, and your
  receipts live in *your* Muse account and never mix with anyone else's.
- Do not upload anyone's private keys to this (or any) repository.
- Before protecting real secrets, read the license and security notes in
  the top-level `README.md`, especially the warning about the ML-KEM
  backend.
