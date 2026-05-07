from __future__ import annotations

import os
from pathlib import Path


TEST_RUNTIME_ROOT = Path(__file__).resolve().parents[1] / ".codeyz_test_runtime"
TEST_RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
os.environ["CODEYZ_RUNTIME_ROOT"] = str(TEST_RUNTIME_ROOT)
