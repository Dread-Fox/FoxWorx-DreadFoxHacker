import pytest
from foxworx.config import Settings
from foxworx.store import Store

@pytest.fixture
def cfg(tmp_path):
    return Settings(state=tmp_path/'state', secret='s'*48, local_token='t'*48, mode='local', reserve_bytes=0,
                    job_timeout=10, config_path=tmp_path/'settings.env')

@pytest.fixture
def store(cfg):
    return Store(cfg.state)

@pytest.fixture
def engagement(store):
    return store.put('engagement', 'local-operator', {'name':'Test lab', 'include':['127.0.0.1'], 'exclude':[], 'notes':''})
