import ast
import asyncio
import json
import time
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.app.services.bambu_mqtt import BambuMQTTClient
from monitor.main import create_app


@pytest.fixture
def web(tmp_path):
    app=create_app(tmp_path,password='unit-test-password',connect_printers=False)
    with TestClient(app) as client:
        client.auth=('admin','unit-test-password')
        yield client,app


def printer_payload(**kwargs):
    return dict(name='Workshop H2D',host='192.168.1.20',serial='testh2d',model='H2D',access_code='12345678',**kwargs)


def spool_payload(**kwargs):
    return dict(name='PETG Blue',initial_g=1000,remaining_g=650,**kwargs)


def test_auth_and_static(web):
    client,_=web
    assert client.get('/api/printers',auth=('admin','wrong')).status_code==401
    assert client.get('/',auth=None).status_code==401
    assert client.get('/').status_code==200
    assert client.get('/static/app.js').status_code==200
    assert client.get('/static/credentials.key').status_code==422
    assert client.get('/health',auth=None).json()['monitoring_only'] is True


def test_credentials_not_exposed_and_edit_keeps_secret(web):
    client,app=web
    response=client.post('/api/printers',json=printer_payload())
    assert response.status_code==201
    row=response.json();assert row['serial']=='TESTH2D'
    assert 'access_code' not in row
    stored=app.state.store.rows('SELECT * FROM printers')[0]
    assert stored['access_code']!='12345678'
    assert app.state.store.secret(stored)=='12345678'
    payload=printer_payload();payload['access_code']='';payload['name']='Renamed'
    assert client.put('/api/printers/1',json=payload).status_code==200
    assert app.state.store.secret(app.state.store.rows('SELECT * FROM printers')[0])=='12345678'
    assert '12345678' not in client.get('/api/printers').text
    assert client.post('/api/printers',json=printer_payload()).status_code==409


def test_inventory_is_local_and_cascades_safely(web):
    client,app=web
    client.post('/api/printers',json=printer_payload())
    response=client.post('/api/spools',json=spool_payload(printer_id=1,slot='AMS 0 / Slot 1'))
    assert response.status_code==201
    assert not app.state.monitor.clients
    assert client.delete('/api/printers/1').status_code==204
    spool=client.get('/api/spools').json()[0]
    assert spool['printer_id'] is None and spool['slot']==''
    assert spool['remaining_g']==650
    assert client.delete('/api/spools/1').status_code==204
    assert client.delete('/api/spools/1').status_code==404


def test_validation_and_csrf(web):
    client,_=web
    invalid=spool_payload();invalid['remaining_g']=1001
    assert client.post('/api/spools',json=invalid).status_code==422
    assert client.post('/api/spools',json=spool_payload(printer_id=999)).status_code==404
    assert client.post('/api/printers',json={**printer_payload(),'developer_mode':True}).status_code==422
    assert client.post('/api/printers',json={**printer_payload(),'serial':'X/+/request'}).status_code==422
    assert client.post('/api/spools',json=spool_payload(),headers={'Origin':'https://evil.example'}).status_code==403
    assert client.post('/api/spools',content='{}',headers={'Content-Type':'text/plain'}).status_code==415


@pytest.mark.parametrize('path',['printers/1/pause','printers/1/stop','printers/1/command','printers/1/ams/filament','printers/1/print','print-queue','scheduled-dryings','smart-plugs','virtual-printers','printers/1/files','cloud/print','printers/1/diagnose'])
def test_control_routes_do_not_exist(web,path):
    client,_=web
    assert client.post('/api/'+path,json={}).status_code==404


def mqtt():
    client=BambuMQTTClient('192.168.1.20','TEST','12345678',model='A1')
    client._client=MagicMock()
    return client


def test_exact_read_request_allowlist():
    client=mqtt()
    client._publish_read_request({'pushing':{'command':'pushall'}})
    client._publish_read_request({'info':{'command':'get_version','sequence_id':'12'}})
    assert client._client.publish.call_count==2
    for payload in [{'print':{'command':'stop'}},{'pushing':{'command':'pushall','gcode':'M140 S100'}},{'pushing':{'command':'pushall'},'print':{'command':'pause'}},{'info':{'command':'get_version','sequence_id':{'command':'stop'}}},{'info':{'command':'get_version','sequence_id':'1','other':'x'}}]:
        with pytest.raises(ValueError):client._publish_read_request(payload)
    assert client._client.publish.call_count==2


def test_actuation_methods_are_physically_removed():
    client=mqtt()
    for name in ['start_print','stop_print','pause_print','resume_print','send_command','send_gcode','publish_raw','set_chamber_light','send_drying_command','ams_set_filament_setting','ams_refresh_tray','set_liveview','execute_hms_action','_probe_developer_mode']:
        assert not hasattr(client,name)
    tree=ast.parse(Path('backend/app/services/bambu_mqtt.py').read_text())
    publishes=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='publish']
    assert len(publishes)==1


@pytest.mark.parametrize('model',['H2C','P2S','X2D','A1','A1 Mini','H2D','H2S','Future Printer'])
def test_connect_and_telemetry_never_send_control(model):
    client=mqtt();client.model=model
    client._on_connect(client._client,None,None,0)
    client._process_message({'print':{'gcode_state':'RUNNING','mc_percent':42,'mc_remaining_time':37,'layer_num':20,'total_layer_num':100,'bed_temper':55,'nozzle_temper':215,'fun':'20000000','ams':{'ams':[{'id':'0','humidity':'3','tray':[{'id':'0','tray_type':'PLA','tray_color':'11FF22FF','remain':73}]}]}}})
    assert client.state.progress==42
    assert client.state.temperatures['bed']==55
    assert client.state.raw_data['ams'][0]['tray'][0]['remain']==73
    client._client.subscribe.assert_called_once_with('device/TEST/report')
    commands=[json.loads(call.args[1]) for call in client._client.publish.call_args_list]
    assert len(commands)==2
    assert commands[0]=={'pushing':{'command':'pushall'}}
    assert commands[1]['info']['command']=='get_version'


def test_partial_ams_data_preserved():
    client=mqtt()
    client._process_message({'print':{'ams':{'ams':[{'id':'0','tray':[{'id':'0','tray_type':'PETG','tray_color':'AABBCCFF','remain':65}]}]},'gcode_state':'RUNNING'}})
    client._process_message({'print':{'mc_percent':48}})
    assert client.state.raw_data['ams'][0]['tray'][0]['tray_type']=='PETG'
    assert client._client.publish.call_count==0


def test_monitor_stale_data_and_history(web):
    client,app=web
    client.post('/api/printers',json=printer_payload())
    mqtt_client=mqtt();mqtt_client.state.connected=True;mqtt_client._last_message_time=time.time()
    mqtt_client._process_message({'print':{'gcode_state':'RUNNING','mc_percent':45,'bed_temper':60}})
    monitor=app.state.monitor;monitor.clients[1]=mqtt_client
    monitor.accept(1,mqtt_client,asdict(mqtt_client.state))
    assert client.get('/api/printers').json()[0]['status']['connected'] is True
    assert len(client.get('/api/printers/1/history').json()['samples'])==1
    monitor.accept(1,mqtt_client,asdict(mqtt_client.state))
    assert len(client.get('/api/printers/1/history').json()['events'])==1
    mqtt_client._last_message_time=time.time()-90
    assert client.get('/api/printers').json()[0]['status']['connected'] is False
    assert client.get('/api/printers/1/camera').status_code==404


def test_camera_is_optional_read_only(web,monkeypatch):
    client,app=web
    client.post('/api/printers',json=printer_payload(camera='rtsp'))
    calls=[]
    async def capture(*args,**kwargs):
        calls.append(args)
        return b'\xff\xd8jpeg\xff\xd9'
    monkeypatch.setattr('monitor.main.capture_camera_frame_bytes',capture)
    assert client.get('/api/printers/1/camera').content==b'\xff\xd8jpeg\xff\xd9'
    assert client.get('/api/printers/1/camera').status_code==200
    assert len(calls)==1
    assert not app.state.monitor.clients


def test_csv_formula_escaping_and_persistence(web):
    client,app=web
    payload=spool_payload();payload['name']='=HYPERLINK("https://example.com")'
    assert client.post('/api/spools',json=payload).status_code==201
    assert "'=HYPERLINK" in client.get('/api/spools.csv').text
    from monitor.store import Store
    again=Store(app.state.store.directory)
    assert again.rows('SELECT * FROM spools')[0]['remaining_g']==650


def test_a1_has_no_invented_chamber_reading(web):
    client,app=web
    payload=printer_payload();payload['model']='A1 Mini'
    client.post('/api/printers',json=payload)
    m=mqtt();m.state.connected=True;m._last_message_time=time.time()
    m._process_message({'print':{'gcode_state':'IDLE','chamber_temper':0}})
    app.state.monitor.clients[1]=m
    app.state.monitor.accept(1,m,asdict(m.state))
    assert 'chamber' not in client.get('/api/printers').json()[0]['status']['temperatures']


def test_disconnected_callbacks_cannot_resurrect_removed_printer(web):
    client,app=web
    client.post('/api/printers',json=printer_payload())
    m=mqtt();app.state.monitor.clients[1]=m
    client.delete('/api/printers/1')
    app.state.monitor.accept(1,m,asdict(m.state))
    assert 1 not in app.state.monitor.status


def test_camera_failure_is_explained_without_mode_requirement(web,monkeypatch):
    client,_=web
    client.post('/api/printers',json=printer_payload(camera='chamber'))
    async def unavailable(*args,**kwargs):return None
    monkeypatch.setattr('monitor.main.capture_camera_frame_bytes',unavailable)
    response=client.get('/api/printers/1/camera')
    assert response.status_code==503
    assert 'not required' in response.json()['detail']
