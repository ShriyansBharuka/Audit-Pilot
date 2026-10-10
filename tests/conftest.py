import json
import os
import tempfile
from pathlib import Path

import pytest

# Fixed test identities, written before anything imports app.gateway (it reads IDENTITIES at import, 04 §2).
TOKENS = {"sal_test": ("sales.priya", "sales"), "whs_test": ("whs.ganesh", "warehouse"),
          "acc_test": ("acc.neha", "accounts"), "adm_test": ("adm.kiran", "client_admin"),
          "aud_test": ("aud.judge", "audit_staff"), "orc_test": ("orc.n8n", "orchestrator"),
          "ptn_test": ("ptn.mehta", "engagement_partner")}
_ids = Path(tempfile.mkdtemp(prefix="auditpilot-ids-")) / "identities.json"
_ids.write_text(json.dumps({t: {"principal": p, "role": r, "name": p} for t, (p, r) in TOKENS.items()}))
os.environ["IDENTITIES"] = str(_ids)

from app import config, db  # noqa: E402


@pytest.fixture()
def world(tmp_path):
    """Fresh, empty 4-database world in a temp dir (COA seeded); restores the default data dir afterwards."""
    default = config.DATA_DIR
    config.set_data_dir(tmp_path)
    db.init_all(reset=True)
    yield tmp_path
    config.set_clock(None)
    config.set_data_dir(default)
