"""Search must find useful tools anywhere in large inventories without prompt growth."""
import json
import time
import threading
from types import SimpleNamespace

import pytest
import foxworx.registry as registry_module


def inventory(count=100):
    rows = [{'name':f'utility-{i:06d}', 'description':'Additional executable',
             'category':'System / additional', 'mode':'unknown', 'package':'',
             'installed':True, 'version':'', 'path':'/bin/true', 'note':''} for i in range(count)]
    rows[-1] = {**rows[-1], 'name':'late-dns-tool', 'description':'DNS records and resolver inspection',
                'category':'DNS', 'mode':'cli'}
    return rows


def discovery(tmp_path, rows):
    assert hasattr(registry_module, 'ToolDiscovery'), 'Backend discovery service is missing'
    reg=SimpleNamespace(scanned=time.time(), list=lambda:rows)
    service=registry_module.ToolDiscovery(reg, tmp_path)
    service.rebuild()
    return service


@pytest.mark.parametrize('count', [4000, 20000, 50000])
def test_large_inventory_retrieval_is_bounded(tmp_path, count):
    service=discovery(tmp_path, inventory(count))
    result=service.shortlist('inspect DNS records')
    assert result['results'][0]['name']=='late-dns-tool'
    assert result['installed_count']==count
    assert result['returned']<=10
    assert len(json.dumps(result).encode())<=32768
    exact=service.search('utility-000042')
    assert exact['results'][0]['name']=='utility-000042'
    service.close()


def test_pagination_counts_filters_and_revision(tmp_path):
    rows=inventory(105)
    service=discovery(tmp_path, rows)
    first=service.search('', limit=40)
    assert first['total_matches']==105 and first['returned']==40
    second=service.search('',limit=40,cursor=first['next_cursor'])
    assert not {r['name'] for r in first['results']} & {r['name'] for r in second['results']}
    third=service.search('',limit=40,cursor=second['next_cursor'])
    assert third['returned']==25 and third['next_cursor'] is None
    assert service.search('',category='DNS',mode='cli')['returned']==1
    assert service.search('no-such-tool')['total_matches']==0
    rows.append({**rows[0], 'name':'new-tool'})
    service.rebuild()
    expired=service.search('',cursor=first['next_cursor'])
    assert expired['restart_required'] and expired['results']==[]
    service.close()


def test_metadata_enrichment_and_missing_metadata(tmp_path):
    rows=inventory(4)
    service=discovery(tmp_path, rows)
    service.rebuild({'utility-000001':{'summary':'Inspect HTTP response headers', 'source':'man', 'version':'1'}})
    found=service.search('HTTP headers')
    assert found['results'][0]['name']=='utility-000001'
    assert found['results'][0]['metadata_sources']==['man']
    assert service.search('utility-000002')['results'][0]['name']=='utility-000002'
    service.close()


def test_bad_inputs_and_query_bound_cursor(tmp_path):
    service=discovery(tmp_path, inventory())
    for kwargs in ({'limit':0},{'limit':41},{'limit':True},{'cursor':'broken'},{'query':[]},{'mode':'invalid'}):
        with pytest.raises(ValueError):service.search(**kwargs)
    page=service.search('',limit=2)
    assert service.search('DNS',cursor=page['next_cursor'])['restart_required']
    service.close()


def test_refresh_is_single_flight_and_keeps_last_snapshot(tmp_path):
    service=discovery(tmp_path,inventory())
    started=threading.Event(); finish=threading.Event();calls=[]
    def scan():
        calls.append(True);started.set();finish.wait(2)
        raise OSError('cannot scan')
    service.registry.scan=scan
    service.registry.scanned=0
    service.metadata_reader=lambda rows,stop:{}
    result=service.search('DNS')
    assert started.wait(1)
    for _ in range(5):service.search('DNS')
    assert calls==[True] and result['stale']
    finish.set();service.close()
    assert service.search('DNS')['results'][0]['name']=='late-dns-tool'


def test_new_inventory_does_not_reuse_old_executable_description(tmp_path):
    rows=inventory(4)
    service=discovery(tmp_path,rows)
    service.rebuild({'utility-000001':{'summary':'special obsolete capability','source':'man'}})
    assert service.search('obsolete')['returned']==1
    service.registry.scanned+=1
    service.rebuild()
    assert service.search('obsolete')['returned']==0
    service.close()


def test_local_metadata_cache_tracks_executable_changes_without_running_it(tmp_path,monkeypatch):
    from foxworx.tool_discovery import LocalMetadata
    import foxworx.tool_discovery as module
    path=tmp_path/'fixture-executable';marker=tmp_path/'executed'
    path.write_text('#!/bin/sh\ntouch '+str(marker)+'\n');path.chmod(0o700)
    summary=['Inspect DNS records']
    def metadata_command(argv):
        if argv[0]=='/usr/bin/whatis':return 'fixture-executable (1) - '+summary[0]+'\n'
        assert argv[0]=='/usr/bin/dpkg-query'
        return ''
    monkeypatch.setattr(module,'_read_command',metadata_command)
    reader=LocalMetadata(tmp_path/'state');stop=threading.Event()
    rows=[{'name':'fixture-executable','path':str(path),'package':'','version':''}]
    assert reader(rows,stop)['fixture-executable']['summary']=='Inspect DNS records'
    summary[0]='Inspect HTTP headers'
    assert reader(rows,stop)['fixture-executable']['summary']=='Inspect DNS records'
    path.write_text(path.read_text()+'# changed executable identity\n')
    assert reader(rows,stop)['fixture-executable']['summary']=='Inspect HTTP headers'
    assert not marker.exists()
    assert reader([],stop)=={}
    summary[0]='Inspect certificates'
    assert reader(rows,stop)['fixture-executable']['summary']=='Inspect certificates'
