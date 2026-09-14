"""End-to-end tests for the freeze → verify → label flow."""

from pathlib import Path

import pytest

from freeze_gate.manifest import build_manifest, load_manifest, write_manifest
from freeze_gate.verify import FAIL, PASS, WARN, run_gate
from freeze_gate.cli import main as cli_main

EXAMPLE_CORE = Path(__file__).resolve().parents[1] / "examples" / "ara-core-example" / "core"


LABELING = {
    "base_model": "example-base-7b",
    "modifications": ["persona overlay: ara", "system prompt pinning"],
    "intended_use": "conversational assistant (demo)",
}


@pytest.fixture
def core_dir(tmp_path):
    core = tmp_path / "core"
    (core / "config").mkdir(parents=True)
    (core / "weights.bin").write_bytes(b"\x00\x01\x02frozen-weights")
    (core / "config" / "persona.yaml").write_text("name: ara\n")
    return core


def freeze(core):
    manifest = build_manifest(
        core, "test-core", "1.0.0", LABELING, parent_core=None, frozen_by="pytest"
    )
    write_manifest(manifest, core)
    return manifest


def test_clean_freeze_passes_gate(core_dir):
    manifest = freeze(core_dir)
    report = run_gate(manifest, core_dir)
    assert report.verdict == PASS
    assert len(report.results) == 5


def test_manifest_lists_all_artifacts_with_digests(core_dir):
    manifest = freeze(core_dir)
    paths = {a["path"] for a in manifest["artifacts"]}
    assert paths == {"weights.bin", "config/persona.yaml"}
    for artifact in manifest["artifacts"]:
        assert len(artifact["sha256"]) == 64
        assert artifact["bytes"] > 0


def test_tampered_artifact_fails_gate(core_dir):
    manifest = freeze(core_dir)
    (core_dir / "weights.bin").write_bytes(b"tampered")
    report = run_gate(manifest, core_dir)
    assert report.verdict == FAIL
    failed = [r for r in report.results if r.status == FAIL]
    assert failed[0].check_id == "FG-002"


def test_deleted_artifact_fails_gate(core_dir):
    manifest = freeze(core_dir)
    (core_dir / "config" / "persona.yaml").unlink()
    report = run_gate(manifest, core_dir)
    assert report.verdict == FAIL


def test_stray_file_fails_gate(core_dir):
    manifest = freeze(core_dir)
    (core_dir / "injected.bin").write_bytes(b"not part of the freeze")
    report = run_gate(manifest, core_dir)
    assert report.verdict == FAIL
    failed = [r for r in report.results if r.status == FAIL]
    assert failed[0].check_id == "FG-003"


def test_missing_labels_warn(core_dir):
    manifest = freeze(core_dir)
    manifest["labeling"]["base_model"] = None
    report = run_gate(manifest, core_dir)
    assert report.verdict == WARN
    warned = [r for r in report.results if r.status == WARN]
    assert any(r.check_id == "FG-004" for r in warned)


def test_unattributed_freeze_warns(core_dir):
    manifest = freeze(core_dir)
    manifest["provenance"]["frozen_by"] = None
    report = run_gate(manifest, core_dir)
    assert report.verdict == WARN


def test_malformed_manifest_fails_structure_check(core_dir):
    report = run_gate({"manifest_version": "1.0"}, core_dir)
    assert report.verdict == FAIL
    assert report.results[0].check_id == "FG-001"


def test_wrong_manifest_version_fails(core_dir):
    manifest = freeze(core_dir)
    manifest["manifest_version"] = "9.9"
    report = run_gate(manifest, core_dir)
    assert report.verdict == FAIL


def test_empty_core_refuses_to_freeze(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError):
        build_manifest(empty, "x", "1", LABELING)


def test_manifest_matches_schema_required_shape(core_dir):
    """The written manifest satisfies the schema's required/shape rules."""
    freeze(core_dir)
    manifest = load_manifest(core_dir)
    for key in ("manifest_version", "core", "labeling", "provenance", "artifacts"):
        assert key in manifest
    assert manifest["manifest_version"] == "1.0"
    assert set(manifest["core"]) == {"id", "version", "frozen_at"}


def test_cli_roundtrip(core_dir, capsys):
    rc = cli_main(
        [
            "freeze",
            str(core_dir),
            "--core-id", "cli-core",
            "--core-version", "0.1.0",
            "--base-model", "example-base-7b",
            "--modification", "persona overlay: ara",
            "--intended-use", "demo",
            "--frozen-by", "pytest",
        ]
    )
    assert rc == 0
    assert cli_main(["verify", str(core_dir), "--strict"]) == 0
    assert cli_main(["label", str(core_dir)]) == 0
    out = capsys.readouterr().out
    assert "gate verdict: PASS" in out
    assert "cli-core" in out


def test_cli_verify_exit_codes(core_dir, capsys):
    freeze(core_dir)
    (core_dir / "weights.bin").write_bytes(b"tampered")
    assert cli_main(["verify", str(core_dir)]) == 1


def test_empty_modifications_is_explicit_none(core_dir):
    """An empty modifications array is a 'none' claim, not an unlabeled field."""
    manifest = freeze(core_dir)
    manifest["labeling"]["modifications"] = []
    report = run_gate(manifest, core_dir)
    assert report.verdict == PASS
    labeling = next(r for r in report.results if r.check_id == "FG-004")
    assert labeling.status == PASS


def test_missing_modifications_warns(core_dir):
    manifest = freeze(core_dir)
    del manifest["labeling"]["modifications"]
    report = run_gate(manifest, core_dir)
    assert report.verdict == WARN
    warned = [r for r in report.results if r.status == WARN]
    assert any(r.check_id == "FG-004" and "modifications" in r.detail for r in warned)


def test_empty_artifacts_fails_structure(core_dir):
    manifest = freeze(core_dir)
    manifest["artifacts"] = []
    report = run_gate(manifest, core_dir)
    assert report.verdict == FAIL
    assert report.results[0].check_id == "FG-001"
    assert len(report.results) == 1


def test_example_core_passes_strict_gate():
    manifest = load_manifest(EXAMPLE_CORE)
    report = run_gate(manifest, EXAMPLE_CORE)
    assert report.verdict == PASS
    assert [r.check_id for r in report.results] == [
        "FG-001",
        "FG-002",
        "FG-003",
        "FG-004",
        "FG-005",
    ]


def test_cli_freeze_without_modifications_is_strict_pass(core_dir):
    rc = cli_main(
        [
            "freeze",
            str(core_dir),
            "--core-id",
            "plain-core",
            "--core-version",
            "1.0.0",
            "--base-model",
            "example-base-7b",
            "--intended-use",
            "demo",
            "--frozen-by",
            "pytest",
        ]
    )
    assert rc == 0
    assert cli_main(["verify", str(core_dir), "--strict"]) == 0


def test_cli_strict_promotes_warn_to_exit_2(core_dir):
    freeze(core_dir)
    manifest = load_manifest(core_dir)
    manifest["provenance"]["frozen_by"] = None
    write_manifest(manifest, core_dir)
    assert cli_main(["verify", str(core_dir)]) == 0
    assert cli_main(["verify", str(core_dir), "--strict"]) == 2


def test_cli_freeze_empty_core_fails(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert (
        cli_main(
            [
                "freeze",
                str(empty),
                "--core-id",
                "x",
                "--core-version",
                "1",
                "--base-model",
                "base",
                "--intended-use",
                "demo",
            ]
        )
        == 1
    )


def test_cli_verify_missing_manifest(tmp_path):
    missing = tmp_path / "core"
    missing.mkdir()
    assert cli_main(["verify", str(missing)]) == 1
