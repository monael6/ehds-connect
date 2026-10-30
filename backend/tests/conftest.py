import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("EHDS_VAR_DIR", tempfile.mkdtemp(prefix="ehds-test-"))

from app import state  # noqa: E402
from app.datastore import DataStore  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"
needs_data = pytest.mark.skipif(not (DATA / "patients.csv").exists(), reason="Track-3 CSVs not in backend/data")


@pytest.fixture(scope="session")
def store():
    if not (DATA / "patients.csv").exists():
        pytest.skip("Track-3 CSVs not in backend/data")
    return DataStore().load()


@pytest.fixture(autouse=True)
def fresh_state():
    state.connect(":memory:")
    yield
