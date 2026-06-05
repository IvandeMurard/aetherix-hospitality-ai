"""Put the repo root on sys.path so eval tests can import `scripts.eval.*`.

The eval tooling lives at repo-root `scripts/eval/`, outside the `backend/`
package root that pytest uses. This conftest runs at collection time.
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]  # backend/tests/eval/ -> repo root
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
