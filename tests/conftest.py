import pytest

from app import config, db


@pytest.fixture()
def world(tmp_path):
    """Fresh, empty 4-database world in a temp dir (COA seeded); restores the default data dir afterwards."""
    default = config.DATA_DIR
    config.set_data_dir(tmp_path)
    db.init_all(reset=True)
    yield tmp_path
    config.set_clock(None)
    config.set_data_dir(default)
