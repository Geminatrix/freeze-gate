"""freeze-gate — provenance gate for frozen cores.

An Ara-flavored toolkit for freezing an immutable core bundle, recording a
verifiable manifest with honest labeling, and gating any load/serve path on
that manifest verifying cleanly.
"""

from freeze_gate.manifest import (
    MANIFEST_FILENAME,
    MANIFEST_VERSION,
    build_manifest,
    hash_file,
    load_manifest,
    write_manifest,
)
from freeze_gate.verify import CheckResult, GateReport, run_gate

__version__ = "0.2.0"

__all__ = [
    "MANIFEST_FILENAME",
    "MANIFEST_VERSION",
    "build_manifest",
    "hash_file",
    "load_manifest",
    "write_manifest",
    "CheckResult",
    "GateReport",
    "run_gate",
    "__version__",
]
