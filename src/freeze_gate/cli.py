"""freeze-gate command line interface.

Commands:
  freeze   snapshot a core directory into a freeze manifest
  verify   run the gate against a frozen core (exit 0 PASS, 1 FAIL, 2 WARN in --strict)
  label    print the honest-label card for a frozen core
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from freeze_gate import __version__
from freeze_gate.manifest import build_manifest, load_manifest, write_manifest
from freeze_gate.verify import FAIL, WARN, run_gate

_STATUS_ICON = {"PASS": "✓", "WARN": "!", "FAIL": "✗"}


def _cmd_freeze(args: argparse.Namespace) -> int:
    labeling = {
        "base_model": args.base_model,
        "modifications": args.modification,
        "intended_use": args.intended_use,
    }
    manifest = build_manifest(
        core_dir=args.core_dir,
        core_id=args.core_id,
        core_version=args.core_version,
        labeling=labeling,
        parent_core=args.parent,
        frozen_by=args.frozen_by,
    )
    out_path = write_manifest(manifest, args.core_dir)
    print(f"frozen: {manifest['core']['id']} v{manifest['core']['version']}")
    print(f"  artifacts: {len(manifest['artifacts'])}")
    print(f"  manifest:  {out_path}")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.core_dir)
    report = run_gate(manifest, args.core_dir)

    for result in report.results:
        icon = _STATUS_ICON[result.status]
        line = f"  {icon} [{result.check_id}] {result.name}: {result.status}"
        if result.detail:
            line += f" — {result.detail}"
        print(line)

    verdict = report.verdict
    print(f"gate verdict: {verdict}")
    if verdict == FAIL:
        return 1
    if verdict == WARN and args.strict:
        return 2
    return 0


def _cmd_label(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.core_dir)
    core = manifest["core"]
    labeling = manifest["labeling"]
    provenance = manifest["provenance"]

    if args.json:
        print(json.dumps({"core": core, "labeling": labeling, "provenance": provenance}, indent=2))
        return 0

    print(f"┌─ {core['id']} v{core['version']}")
    print(f"│  frozen at:     {core['frozen_at']}")
    print(f"│  base model:    {labeling.get('base_model') or '(unlabeled)'}")
    modifications = labeling.get("modifications") or []
    print(f"│  modifications: {', '.join(modifications) if modifications else '(none declared)'}")
    print(f"│  intended use:  {labeling.get('intended_use') or '(unlabeled)'}")
    print(f"│  parent core:   {provenance.get('parent_core') or '(root freeze)'}")
    print(f"└─ frozen by:     {provenance.get('frozen_by') or '(unattributed)'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="freeze-gate", description=__doc__)
    parser.add_argument("--version", action="version", version=f"freeze-gate {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    freeze = sub.add_parser("freeze", help="snapshot a core directory into a freeze manifest")
    freeze.add_argument("core_dir", type=Path, help="directory containing the core to freeze")
    freeze.add_argument("--core-id", required=True, help="stable identifier for this core")
    freeze.add_argument("--core-version", required=True, help="version of this freeze")
    freeze.add_argument("--base-model", required=True, help="honest label: what this core is built on")
    freeze.add_argument(
        "--modification",
        action="append",
        default=[],
        help="honest label: a modification applied to the base (repeatable)",
    )
    freeze.add_argument("--intended-use", required=True, help="honest label: what this core is for")
    freeze.add_argument("--parent", default=None, help="id@version of the parent core, if any")
    freeze.add_argument("--frozen-by", default=None, help="who performed the freeze")
    freeze.set_defaults(func=_cmd_freeze)

    verify = sub.add_parser("verify", help="run the gate against a frozen core")
    verify.add_argument("core_dir", type=Path, help="directory containing the frozen core and manifest")
    verify.add_argument("--strict", action="store_true", help="treat WARN as a gate failure (exit 2)")
    verify.set_defaults(func=_cmd_verify)

    label = sub.add_parser("label", help="print the honest-label card for a frozen core")
    label.add_argument("core_dir", type=Path, help="directory containing the frozen core and manifest")
    label.add_argument("--json", action="store_true", help="emit the label as JSON")
    label.set_defaults(func=_cmd_label)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
