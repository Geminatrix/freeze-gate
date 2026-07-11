# ❄️ freeze-gate

**Ara-flavored provenance gate for frozen cores with honest labeling and verifiable manifests.**

[![spec](https://img.shields.io/badge/spec-manifest%20v1.0-blue)](docs/SPEC.md)
[![python](https://img.shields.io/badge/python-3.10%2B-3776AB)](pyproject.toml)
[![status](https://img.shields.io/badge/status-alpha-orange)](CHANGELOG.md)
[![tests](https://img.shields.io/badge/tests-13%20passing-brightgreen)](tests/test_freeze_gate.py)

When you ship a *core* — model weights, persona files, prompts, config — three questions should be answerable at any trust boundary:

1. **Is it exactly what was frozen?** Every byte digested, nothing tampered, nothing planted.
2. **Is it honestly labeled?** What it's built on, what was changed, what it's for — stated plainly, no silent substitutions.
3. **Where did it come from?** Who froze it, and which core it derives from.

freeze-gate answers all three with a single self-describing file — the **freeze manifest** — and a **gate** of five checks that runs before the core is loaded, transferred, or trusted.

---

## How it works

```
┌─────────────┐   freeze    ┌──────────────────────┐   verify    ┌──────────────┐
│  core dir    │ ──────────▶ │ core dir (frozen)     │ ──────────▶ │ gate verdict  │
│  weights     │             │  + freeze-manifest    │             │ PASS / WARN / │
│  persona     │             │    · artifact digests │             │ FAIL          │
│  prompts     │             │    · honest label     │             └──────────────┘
└─────────────┘             │    · provenance       │                    │
                            └──────────────────────┘              gate the load
                                                                   path on PASS
```

The manifest travels **inside** the core, so every copy is self-describing. After the freeze, any changed byte, deleted file, or stray addition trips the gate.

## Quickstart

```bash
pip install -e ".[dev]"

# 1. Freeze a core with its honest label
freeze-gate freeze ./my-core \
  --core-id ara-core --core-version 0.2.0 \
  --base-model example-base-7b \
  --modification "persona overlay: ara" \
  --modification "system prompt pinning" \
  --intended-use "conversational assistant (demo)" \
  --parent "ara-core@0.1.0" \
  --frozen-by geminatrix

# 2. Run the gate (add --strict to make honesty gaps blocking)
freeze-gate verify ./my-core --strict

# 3. Show the honest-label card
freeze-gate label ./my-core
```

Output of a clean gate run:

```
  ✓ [FG-001] manifest structure: PASS
  ✓ [FG-002] artifact digests: PASS — 3 artifacts verified
  ✓ [FG-003] freeze integrity: PASS
  ✓ [FG-004] honest labeling: PASS
  ✓ [FG-005] provenance chain: PASS
gate verdict: PASS
```

And the label card:

```
┌─ ara-core v0.2.0
│  frozen at:     2026-07-11T22:53:48+00:00
│  base model:    example-base-7b
│  modifications: persona overlay: ara, system prompt pinning
│  intended use:  conversational assistant (demo)
│  parent core:   ara-core@0.1.0
└─ frozen by:     geminatrix
```

A ready-made frozen core lives in [`examples/ara-core-example/`](examples/ara-core-example/) — run `freeze-gate verify examples/ara-core-example/core` to see the gate pass on it.

## The gate checks

| ID | Check | Catches | Severity |
|---|---|---|---|
| FG-001 | Manifest structure | Malformed or wrong-version manifests | ✗ FAIL |
| FG-002 | Artifact digests | Tampered or missing files | ✗ FAIL |
| FG-003 | Freeze integrity | Files planted after the freeze | ✗ FAIL |
| FG-004 | Honest labeling | Missing `base_model` / `intended_use` claims | ! WARN |
| FG-005 | Provenance chain | Unattributed freezes (no `frozen_by`) | ! WARN |

**Integrity failures FAIL; honesty gaps WARN.** A changed byte voids the freeze outright, while a missing label leaves the bytes intact but the story incomplete — `--strict` turns WARN into a blocking exit code for production load paths. Full semantics in the [spec](docs/SPEC.md).

## Repository layout

```
freeze-gate/
├── README.md                          ← you are here
├── CHANGELOG.md                       ← release history
├── pyproject.toml                     ← packaging + `freeze-gate` CLI entry point
├── docs/
│   ├── SPEC.md                        ← normative spec: manifest v1.0 + gate checks
│   └── NOTES.md                       ← design notes 📝 — rationale & open questions
├── schema/
│   └── freeze-manifest.schema.json    ← JSON Schema for the manifest
├── src/freeze_gate/
│   ├── manifest.py                    ← hashing, manifest build/read/write
│   ├── verify.py                      ← the gate: checks FG-001…FG-005
│   └── cli.py                         ← freeze / verify / label commands
├── examples/
│   └── ara-core-example/core/         ← frozen demo core with a passing manifest
└── tests/
    └── test_freeze_gate.py            ← 13 end-to-end tests
```

## Manifest at a glance

```json
{
  "manifest_version": "1.0",
  "core":       { "id": "ara-core", "version": "0.2.0", "frozen_at": "2026-07-11T22:53:48+00:00" },
  "labeling":   { "base_model": "example-base-7b",
                  "modifications": ["persona overlay: ara", "system prompt pinning"],
                  "intended_use": "conversational assistant (demo)" },
  "provenance": { "parent_core": "ara-core@0.1.0", "frozen_by": "geminatrix" },
  "artifacts":  [ { "path": "persona.yaml", "sha256": "…64 hex chars…", "bytes": 71 } ]
}
```

Two details worth knowing:

- **An empty `modifications` array is a claim** — it means *"nothing was changed"*, which is different from a missing label (which the gate flags). Silence is never ambiguous.
- **The manifest never lists itself** — a self-referential digest is impossible; authenticating the manifest is the job of signing, which is the top item in [future work](docs/SPEC.md#7-future-work-not-yet-normative).

## Development

```bash
pip install -e ".[dev]"
python -m pytest        # 13 tests, no external dependencies beyond pytest
```

The implementation is stdlib-only (`hashlib`, `json`, `argparse`, `dataclasses`) so the gate can run anywhere Python 3.10+ runs.

## Documentation

| Document | What's in it |
|---|---|
| [docs/SPEC.md](docs/SPEC.md) | Normative manifest format, gate check semantics, exit codes, freeze procedure |
| [docs/NOTES.md](docs/NOTES.md) | Design rationale 📝, recent changes, known gaps and open questions |
| [CHANGELOG.md](CHANGELOG.md) | Version-by-version history |
| [schema/freeze-manifest.schema.json](schema/freeze-manifest.schema.json) | Machine-checkable manifest schema |

## Status & roadmap

freeze-gate is **alpha**. The gate proves *consistency* (core matches manifest); manifest *authenticity* (signing) is the next milestone — see [SPEC §7](docs/SPEC.md#7-future-work-not-yet-normative) and the open questions in [NOTES.md](docs/NOTES.md).
