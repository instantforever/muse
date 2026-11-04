# Third-party notices

This project is distributed under the MIT License (see `LICENSE`).
The components below are **not** covered by that license; they keep their
own licenses and copyright notices. This file is a summary for convenience
only and is not legal advice — check the upstream license text for the
exact versions you use or redistribute.

## Python engine (`lenc-pipeline/`)

| Component | Used for | License |
|---|---|---|
| [cryptography](https://pypi.org/project/cryptography/) (PyCA) | RSA-OAEP, Ed25519 / Ed448, X25519 / X448, AES-256-GCM, HKDF | Dual-licensed **Apache License 2.0 OR BSD 3-Clause** (you may choose either). Its binary wheels statically link **OpenSSL**, which since OpenSSL 3.0 is licensed under **Apache License 2.0**. |
| [kyber-py](https://pypi.org/project/kyber-py/) | ML-KEM (FIPS 203) in pure Python | Dual-licensed **MIT OR Apache License 2.0** (your choice). **Upstream warning:** the author describes it as an educational resource that has not been designed to be secure and states it should under no circumstances be used for cryptographic applications. Treat ML-KEM support here as experimental; prefer an audited implementation (e.g. liboqs) for real use. |

## Artifact (browser side, when recreated from `artifact/ARTIFACT_SPEC.md`)

The in-browser cryptography of the artifact is expected to be implemented
with the **noble** family of TypeScript libraries
(`@noble/curves`, `@noble/hashes`, `@noble/ciphers`, `@noble/post-quantum`),
all licensed under the **MIT License**, Copyright (c) Paul Miller.
If a recreation uses different libraries, their notices must be added here
by whoever builds and redistributes that build.

General redistribution notes for MIT / Apache-2.0 / BSD components:
keep the copyright and license notices in copies, include the license
texts when redistributing binaries or substantial portions, and note that
Apache-2.0 additionally includes a patent grant and requires stating
significant changes. None of these licenses is copyleft: they do not force
you to open-source your own code, but they do not grant trademark rights,
and the software is provided without warranty.

## Standards (no code copied)

AES-GCM (NIST SP 800-38D), RSA-OAEP (RFC 8017), Ed25519 / Ed448
(RFC 8032), X25519 / X448 (RFC 7748), HKDF (RFC 5869) and ML-KEM
(NIST FIPS 203) are public specifications. This project implements /
calls them through the libraries above.
