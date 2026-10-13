import os
import pytest
from fastapi import HTTPException
from foxworx.evidence import safe_open

def test_fifo_download_is_rejected_without_a_blocking_open(tmp_path,monkeypatch):
    os.mkfifo(tmp_path/'pipe')
    real_open=os.open
    def checked_open(path,flags,*args,**kwargs):
        if str(path)=='pipe':
            assert flags & os.O_NONBLOCK, 'Opening a FIFO before checking its type could hang the request'
        return real_open(path,flags,*args,**kwargs)
    monkeypatch.setattr(os,'open',checked_open)
    with pytest.raises(HTTPException) as e: safe_open(tmp_path,'pipe')
    assert e.value.status_code==400

def test_directory_symlink_not_followed(tmp_path):
    (tmp_path/'jump').symlink_to('/etc',target_is_directory=True)
    with pytest.raises(HTTPException): safe_open(tmp_path,'jump/passwd')
