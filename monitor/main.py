"""Small monitoring-only runtime. No upstream command routes or workers load."""
import asyncio
import csv
import io
import json
import logging
import os
import re
import secrets
import sqlite3
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.services.bambu_mqtt import BambuMQTTClient
from backend.app.services.camera import capture_camera_frame_bytes
from backend.app.utils.ams_humidity import ams_humidity_percent
from monitor import __version__
from monitor.store import Store

log = logging.getLogger(__name__)
security = HTTPBasic(auto_error=False)
STATIC = Path(__file__).parent / 'static'


class PrinterInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    host: str = Field(min_length=1, max_length=253, pattern=r'^[a-zA-Z0-9][a-zA-Z0-9.\-]*$')
    serial: str = Field(min_length=1, max_length=50, pattern=r'^[a-zA-Z0-9]+$')
    model: str = Field(default='', max_length=50)
    access_code: str = Field(default='', max_length=32, pattern=r'^[a-zA-Z0-9]*$')
    camera: Literal['off', 'rtsp', 'chamber'] = 'off'


class SpoolInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, allow_inf_nan=False)
    name: str = Field(min_length=1, max_length=100)
    brand: str = Field(default='', max_length=100)
    material: str = Field(default='PLA', min_length=1, max_length=40)
    color: str = Field(default='#22c55e', pattern=r'^#[0-9a-fA-F]{6}$')
    initial_g: float = Field(ge=0, le=100000)
    remaining_g: float = Field(ge=0, le=100000)
    location: str = Field(default='', max_length=100)
    notes: str = Field(default='', max_length=2000)
    printer_id: int | None = Field(default=None, gt=0)
    slot: str = Field(default='', max_length=50)

    @model_validator(mode='after')
    def weights(self):
        if self.remaining_g > self.initial_g:
            raise ValueError('Remaining weight cannot exceed starting weight')
        return self


class Monitor:
    def __init__(self, store):
        self.store = store
        self.clients = {}
        self.status = {}
        self.sample_times = {}
        self.camera_cache = {}
        self.camera_locks = {}

    def accept(self, pid, source, state):
        if self.clients.get(pid) is not source:
            return  # Ignore callbacks from an edited/deleted connection.
        previous = self.status.get(pid, {})
        state['last_seen'] = source._last_message_time or None
        state['connected'] = bool(state['connected'] and not source.is_stale() and state['last_seen'])
        self.status[pid] = state
        if state.get('last_seen') and state['connected']:
            label = state.get('subtask_name') or state.get('current_print') or ''
            if (state['state'], label) != (previous.get('state'), previous.get('subtask_name') or previous.get('current_print') or ''):
                with self.store.connect() as db:
                    db.execute('INSERT INTO events(printer_id,name,state) VALUES(?,?,?)', (pid,label,state['state']))
                    db.execute('DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT 5000)')
            if time.time() - self.sample_times.get(pid, 0) >= 60:
                self.sample_times[pid] = time.time()
                t = state.get('temperatures', {})
                with self.store.connect() as db:
                    db.execute('INSERT INTO samples(printer_id,bed,nozzle,progress) VALUES(?,?,?,?)', (pid,t.get('bed'),t.get('nozzle'),state.get('progress')))
                    db.execute("DELETE FROM samples WHERE observed_at < datetime('now','-30 days')")

    def connect(self, row):
        self.disconnect(row['id'])
        loop = asyncio.get_running_loop()
        client = BambuMQTTClient(row['host'], row['serial'], self.store.secret(row), model=row['model'])
        def changed(state):
            # Copy on paho's thread; the event loop never iterates mutable parser data.
            snapshot = asdict(state)
            loop.call_soon_threadsafe(self.accept, row['id'], client, snapshot)
        client.on_state_change = changed
        self.clients[row['id']] = client
        client.connect(loop)

    def disconnect(self, pid):
        client = self.clients.pop(pid, None)
        if client:
            client.disconnect()
        self.status.pop(pid, None)
        self.camera_cache.pop(pid, None)
        self.sample_times.pop(pid, None)

    def public(self, row):
        result = {k:v for k,v in row.items() if k != 'access_code'}
        state = self.status.get(row['id'])
        if state:
            state = dict(state)
            client = self.clients.get(row['id'])
            state['connected'] = bool(client and client.state.connected and not client.is_stale() and state.get('last_seen'))
            # Expose telemetry only, never raw request traffic or action suggestions.
            allowed = {'connected','state','current_print','subtask_name','progress','remaining_time','layer_num','total_layers','temperatures','hms_errors','firmware_version','nozzle_rack','last_seen','ams_extruder_map','extruder_slots','cooling_fan_speed','big_fan1_speed','big_fan2_speed'}
            result['status'] = {k:v for k,v in state.items() if k in allowed}
            for error in result['status'].get('hms_errors', []):
                error.pop('actions', None)
            # A1/P1 may emit a chamber field despite having no chamber sensor.
            model = re.sub(r'[^A-Z0-9]', '', row['model'].upper())
            if model in {'A1','A1MINI','N1','N2S','P1P','P1S','C11','C12'}:
                result['status']['temperatures'] = {k:v for k,v in state.get('temperatures', {}).items() if not k.startswith('chamber')}
            raw = state.get('raw_data', {})
            units = raw.get('ams', [])
            if isinstance(units, dict):
                units = units.get('ams', [])
            result['status']['ams'] = [dict(u, humidity_percent=ams_humidity_percent(u)) for u in units if isinstance(u, dict)]
            result['status']['external_spools'] = raw.get('vt_tray', [])
        else:
            result['status'] = {'connected':False, 'state':'Waiting for telemetry','last_seen':None}
        client = self.clients.get(row['id'])
        result['connection_error'] = client.last_connect_error_name if client else None
        return result


def create_app(data_dir=None, password=None, connect_printers=True):
    password = password if password is not None else os.environ.get('BAMBUDDY_PASSWORD', '')
    username = os.environ.get('BAMBUDDY_USERNAME', 'admin')
    store = Store(data_dir or os.environ.get('DATA_DIR', './data'))
    monitor = Monitor(store)

    async def authenticate(credentials: HTTPBasicCredentials | None = Depends(security)):
        if not password:
            return
        if credentials is None or not (secrets.compare_digest(credentials.username.encode(), username.encode()) & secrets.compare_digest(credentials.password.encode(), password.encode())):
            raise HTTPException(401, 'Incorrect username or password', headers={'WWW-Authenticate':'Basic'})

    async def watchdog():
        while True:
            await asyncio.sleep(15)
            for client in list(monitor.clients.values()):
                client.check_staleness()

    @asynccontextmanager
    async def lifespan(app):
        if connect_printers:
            for row in store.rows('SELECT * FROM printers'):
                monitor.connect(row)
        task = asyncio.create_task(watchdog())
        yield
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        for pid in list(monitor.clients):
            monitor.disconnect(pid)

    app = FastAPI(title='Bambuddy Monitor', version=__version__, lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.monitor = monitor
    app.state.store = store

    @app.middleware('http')
    async def headers(request: Request, call_next):
        # JSON-only mutations and same-origin browser requests avoid Basic-auth CSRF.
        if request.method in {'POST','PUT','DELETE'}:
            origin = request.headers.get('origin')
            if origin and origin.rstrip('/') != str(request.base_url).rstrip('/'):
                return Response(status_code=403)
            if request.method != 'DELETE' and request.headers.get('content-type','').split(';')[0] != 'application/json':
                return Response(status_code=415)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self'; img-src 'self' data: blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'self'"
        return response

    @app.get('/health')
    def health():
        return {'status':'ok','version':__version__,'monitoring_only':True}

    def printer(pid):
        rows = store.rows('SELECT * FROM printers WHERE id=?', (pid,))
        if not rows:
            raise HTTPException(404, 'Printer not found')
        return rows[0]

    @app.get('/', dependencies=[Depends(authenticate)])
    def index():
        return FileResponse(STATIC / 'index.html')

    @app.get('/static/{name}', dependencies=[Depends(authenticate)])
    def static(name: Literal['app.js','style.css']):
        return FileResponse(STATIC / name)

    @app.get('/api/printers', dependencies=[Depends(authenticate)])
    def printers():
        return [monitor.public(row) for row in store.rows('SELECT * FROM printers ORDER BY name')]

    async def save_printer(payload, pid=None):
        values = payload.model_dump()
        values['serial'] = values['serial'].upper()
        old = printer(pid) if pid else None
        if not values['access_code'] and not old:
            raise HTTPException(422, 'An access code is required')
        values['access_code'] = store.encrypt(values['access_code']) if values['access_code'] else old['access_code']
        try:
            with store.connect() as db:
                if pid:
                    db.execute('UPDATE printers SET '+','.join(f'{k}=?' for k in values)+' WHERE id=?', (*values.values(),pid))
                else:
                    pid = db.execute('INSERT INTO printers('+','.join(values)+') VALUES('+','.join('?' for _ in values)+')',tuple(values.values())).lastrowid
        except sqlite3.IntegrityError:
            raise HTTPException(409, 'A printer with that serial number already exists')
        row = printer(pid)
        if connect_printers:
            monitor.connect(row)
        return monitor.public(row)

    @app.post('/api/printers', dependencies=[Depends(authenticate)], status_code=201)
    async def add_printer(payload: PrinterInput):
        return await save_printer(payload)

    @app.put('/api/printers/{pid}', dependencies=[Depends(authenticate)])
    async def edit_printer(pid: int, payload: PrinterInput):
        return await save_printer(payload,pid)

    @app.delete('/api/printers/{pid}', dependencies=[Depends(authenticate)], status_code=204)
    async def delete_printer(pid: int):
        printer(pid)
        monitor.disconnect(pid)
        with store.connect() as db:
            db.execute("UPDATE spools SET slot='' WHERE printer_id=?", (pid,))
            db.execute('DELETE FROM printers WHERE id=?', (pid,))

    @app.get('/api/printers/{pid}/history', dependencies=[Depends(authenticate)])
    def history(pid: int):
        printer(pid)
        return {'events':store.rows('SELECT name,state,observed_at FROM events WHERE printer_id=? ORDER BY id DESC LIMIT 100',(pid,)), 'samples':store.rows('SELECT bed,nozzle,progress,observed_at FROM samples WHERE printer_id=? ORDER BY id DESC LIMIT 120',(pid,))[::-1]}

    @app.get('/api/printers/{pid}/camera', dependencies=[Depends(authenticate)])
    async def camera(pid: int):
        row = printer(pid)
        if row['camera'] == 'off':
            raise HTTPException(404, 'Camera is not enabled in this app')
        lock = monitor.camera_locks.setdefault(pid, asyncio.Lock())
        async with lock:
            cached = monitor.camera_cache.get(pid)
            if not cached or time.monotonic()-cached[0] > 5:
                # Explicit protocol selection also supports unknown future model names.
                model = 'A1' if row['camera'] == 'chamber' else 'H2D'
                frame = await capture_camera_frame_bytes(row['host'],store.secret(row),model,timeout=12)
                cached = (time.monotonic(),frame)
                monitor.camera_cache[pid] = cached
            if not cached[1]:
                raise HTTPException(503, 'Camera unavailable. Check local liveview, access code and network; firmware may restrict the feed. Developer Mode is not required by this app.')
            return Response(cached[1],media_type='image/jpeg')

    @app.get('/api/spools', dependencies=[Depends(authenticate)])
    def spools():
        return store.rows('SELECT * FROM spools ORDER BY name')

    def save_spool(payload,pid=None):
        values = payload.model_dump()
        if values['printer_id']:
            printer(values['printer_id'])
        elif values['slot']:
            raise HTTPException(422, 'Select a printer for the local slot label')
        with store.connect() as db:
            if pid:
                if not db.execute('SELECT id FROM spools WHERE id=?',(pid,)).fetchone():
                    raise HTTPException(404, 'Spool not found')
                db.execute('UPDATE spools SET '+','.join(f'{k}=?' for k in values)+',updated_at=CURRENT_TIMESTAMP WHERE id=?',(*values.values(),pid))
            else:
                pid=db.execute('INSERT INTO spools('+','.join(values)+') VALUES('+','.join('?' for _ in values)+')',tuple(values.values())).lastrowid
        return store.rows('SELECT * FROM spools WHERE id=?',(pid,))[0]

    @app.post('/api/spools', dependencies=[Depends(authenticate)], status_code=201)
    def add_spool(payload: SpoolInput):
        return save_spool(payload)

    @app.put('/api/spools/{sid}', dependencies=[Depends(authenticate)])
    def edit_spool(sid: int,payload: SpoolInput):
        return save_spool(payload,sid)

    @app.delete('/api/spools/{sid}', dependencies=[Depends(authenticate)], status_code=204)
    def delete_spool(sid: int):
        with store.connect() as db:
            if not db.execute('DELETE FROM spools WHERE id=?',(sid,)).rowcount:
                raise HTTPException(404, 'Spool not found')

    @app.get('/api/spools.csv', dependencies=[Depends(authenticate)])
    def export_spools():
        rows = spools()
        columns = list(SpoolInput.model_fields)
        output=io.StringIO()
        writer=csv.writer(output)
        writer.writerow(columns)
        def safe(value):
            if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')):
                return "'"+value
            return value
        for row in rows:
            writer.writerow([safe(row[c]) for c in columns])
        return Response(output.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="filament-inventory.csv"'})

    return app
