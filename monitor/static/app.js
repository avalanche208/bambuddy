'use strict';
const $ = id => document.getElementById(id);
let printers=[],spools=[],editor=null,detailId=null,cameraTimer=null,pollTimer=null,refreshing=false;
const esc = v => String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num = (v,suffix='') => v!==null&&v!==undefined&&Number.isFinite(Number(v)) ? `${Math.round(Number(v))}${suffix}` : '—';
const stamp = v => v ? new Date(v.includes?.('T')?v:`${v.replace(' ','T')}Z`).toLocaleString() : '—';
const color = v => /^[0-9a-f]{6,8}$/i.test(v||'') ? '#'+v.slice(0,6) : '#718078';
// Color swatches use SVG attributes so no inline styles are needed under CSP.
const swatch = c => `<svg class="swatch" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="10" fill="${esc(c)}"/></svg>`;
async function api(path,method='GET',data){
 const res=await fetch('/api/'+path,{method,headers:data?{'Content-Type':'application/json'}:{},body:data?JSON.stringify(data):undefined});
 if(!res.ok){let value;try{value=await res.json();}catch{}throw Error(typeof value?.detail==='string'?value.detail:`Request failed (${res.status}). Check the entered values and connection.`);}
 return res.status===204?null:res.json();
}
function notice(message){$('notice').textContent=message||'';$('notice').hidden=!message;}
async function refresh(){
 if(refreshing)return;refreshing=true;
 try{[printers,spools]=await Promise.all([api('printers'),api('spools')]);render();$('connection').textContent='Updated '+new Date().toLocaleTimeString();notice('');}
 catch(e){$('connection').textContent='Connection unavailable';notice(e.message);}
 finally{refreshing=false;}
}
function tray(t,label){
 const remaining=Number(t.remain);const known=t.remain!==null&&t.remain!==undefined&&remaining>=0&&remaining<=100;
 return `<div class="tray">${swatch(color(t.tray_color))}<span>${esc(label)} · ${esc(t.tray_type||'Unknown / unconfigured')}</span><span class="subtle">${known?num(remaining,'% est.'):'Amount unknown'}</span></div>`;
}
function render(){
 const online=printers.filter(p=>p.status.connected).length,printing=printers.filter(p=>p.status.connected&&['RUNNING','PREPARE','SLICING'].includes(String(p.status.state).toUpperCase())).length;
 $('summary').innerHTML=[[printers.length,'PRINTERS'],[online,'ONLINE'],[printing,'PRINTING'],[spools.length,'SPOOLS IN INVENTORY']].map(([v,l])=>`<div class="stat"><strong>${v}</strong><span>${l}</span></div>`).join('');
 const query=$('printer-search').value.toLowerCase();
 $('printers').innerHTML=printers.filter(p=>`${p.name} ${p.model}`.toLowerCase().includes(query)).map(p=>{
 const s=p.status,live=s.connected,hasData=!!s.last_seen,t=s.temperatures||{},ams=s.ams||[],ext=s.external_spools||[];
 const errors=s.hms_errors||[];
 return `<article class="card"><div class="card-top"><div><h3>${esc(p.name)}</h3><span class="subtle">${esc(p.model||'Generic Bambu')} · ${esc(p.host)}</span></div><span class="pill ${live?'':'offline'}">${esc(live?s.state:hasData?'Offline':'Waiting')}</span></div><div class="job">${esc(s.subtask_name||s.current_print||(live?'No active print':'Waiting for printer telemetry'))}</div><progress max="100" value="${live?Math.max(0,Math.min(100,Number(s.progress)||0)):0}" aria-label="Print progress"></progress><div class="metrics"><div><strong>${live?num(s.progress,'%'):'—'}</strong><small>PROGRESS</small></div><div><strong>${live?num(s.remaining_time,' min'):'—'}</strong><small>REMAINING</small></div><div><strong>${live?num(s.layer_num):'—'}<small> / ${live?num(s.total_layers):'—'}</small></strong><small>LAYER</small></div></div><div class="metrics"><div><strong>${live?num(t.nozzle,'°'):'—'}</strong><small>NOZZLE</small></div><div><strong>${live?num(t.bed,'°'):'—'}</strong><small>BED</small></div><div><strong>${live?num(t.chamber,'°'):'—'}</strong><small>CHAMBER</small></div></div>${errors.length?`<p class="error">${errors.length} reported alert${errors.length===1?'':'s'}</p>`:''}${p.connection_error?`<p class="error">${esc(p.connection_error)} — check access code and network.</p>`:''}<div class="tray-list">${!live&&hasData?'<p class="subtle">Last reported filament data · printer offline</p>':''}${ams.map(u=>`<div class="ams">AMS ${esc(u.id)} · ${u.humidity_percent!=null?num(u.humidity_percent,'% humidity'):u.humidity!=null?'Humidity level '+esc(u.humidity):'Humidity unknown'} · ${num(u.temp,'°C')}${u.dry_time?` · Drying ${num(u.dry_time,' min')}`:''}</div>${(u.tray||[]).map(t=>tray(t,`Slot ${Number(t.id)+1}`)).join('')}`).join('')}${ext.map((t,i)=>tray(t,`External ${i+1}`)).join('')}${!ams.length&&!ext.length?'<p class="subtle">Filament telemetry not yet available</p>':''}</div><div class="actions"><button class="secondary" data-action="detail" data-id="${p.id}">Details${p.camera!=='off'?' & camera':''}</button><button class="secondary" data-action="edit-printer" data-id="${p.id}">Edit connection</button></div><p class="subtle">${s.last_seen?'Last report '+new Date(s.last_seen*1000).toLocaleTimeString():'No status received yet'}${s.firmware_version?' · FW '+esc(s.firmware_version):''}</p></article>`;
 }).join('')||'<div class="empty">No printers to display. Add a printer using its local connection details.</div>';
 const search=$('spool-search').value.toLowerCase();
 $('spools').innerHTML=spools.filter(s=>`${s.name} ${s.brand} ${s.material} ${s.location}`.toLowerCase().includes(search)).map(s=>`<article class="card"><div class="card-top"><div><h3>${esc(s.name)}</h3><span class="subtle">${esc(s.brand)} · ${esc(s.material)}</span></div>${swatch(s.color)}</div><div class="spool-weight">${num(s.remaining_g)} <small class="subtle">g remaining</small></div><progress max="${s.initial_g||1}" value="${s.remaining_g}" aria-label="Recorded filament remaining"></progress><p class="subtle">${num(s.initial_g)} g starting weight · manually recorded</p><p>${esc(s.location||'No storage location')}${s.printer_id?' · '+esc(printers.find(p=>p.id===s.printer_id)?.name||'Unknown printer')+' / '+esc(s.slot||'No slot label'):''}</p>${s.notes?`<p class="subtle">${esc(s.notes)}</p>`:''}<div class="actions"><button class="secondary" data-action="edit-spool" data-id="${s.id}">Edit / update weight</button></div></article>`).join('')||'<div class="empty">No matching spools. Add your filament to start tracking inventory.</div>';
}
function field(name,label,value='',type='text',extra=''){
 return `<label>${esc(label)}<input name="${name}" type="${type}" value="${esc(value)}" ${extra}></label>`;
}
function openEditor(kind,item=null){
 editor={kind,id:item?.id};$('editor-title').textContent=(item?'Edit ':'Add ')+(kind==='printer'?'printer':'spool');$('form-error').textContent='';
 if(kind==='printer'){
 const p=item||{};
 $('fields').innerHTML=field('name','Printer name',p.name,'text','required maxlength="100"')+field('model','Model (or a future model name)',p.model,'text','list="models"')+'<datalist id="models">'+['H2C','P2S','X2D','A1','A1 Mini','H2D','H2S'].map(m=>`<option>${m}</option>`).join('')+'</datalist>'+field('host','IP address or hostname',p.host,'text','required')+field('serial','Serial number',p.serial,'text','required')+field('access_code',item?'Access code (blank keeps existing)':'Access code','','password',item?'autocomplete="new-password"':'required autocomplete="new-password"')+`<label>Local camera<select name="camera">${[['off','Off'],['rtsp','RTSPS — H2 / P2S / X2D'],['chamber','Chamber JPEG — A1 / A1 Mini']].map(([v,l])=>`<option value="${v}" ${p.camera===v?'selected':''}>${l}</option>`).join('')}</select></label><p class="wide subtle">Developer Mode is not needed. For supported cameras, enable local liveview on the printer. Camera access is optional and may vary with firmware.</p>`;
 }else{
 const s=item||{initial_g:1000,remaining_g:1000,color:'#22c55e',material:'PLA'};
 $('fields').innerHTML=field('name','Spool name',s.name,'text','required maxlength="100"')+field('brand','Brand',s.brand)+field('material','Material',s.material,'text','required')+field('color','Color',s.color,'color')+field('initial_g','Starting filament weight (g)',s.initial_g,'number','required min="0" max="100000" step="0.1"')+field('remaining_g','Remaining filament weight (g)',s.remaining_g,'number','required min="0" max="100000" step="0.1"')+field('location','Storage location',s.location)+`<label>Printer (local label only)<select name="printer_id"><option value="">Unassigned</option>${printers.map(p=>`<option value="${p.id}" ${s.printer_id===p.id?'selected':''}>${esc(p.name)}</option>`).join('')}</select></label>`+field('slot','Slot label (for example AMS 0 / Slot 1)',s.slot)+`<label class="wide">Notes<textarea name="notes" maxlength="2000">${esc(s.notes)}</textarea></label><p class="wide subtle">Weights are local records, separate from the printer’s estimated percentage. Updating a spool or label never writes to the AMS.</p>`;
 }
 if(item)$('fields').insertAdjacentHTML('beforeend','<div class="wide"><button type="button" class="secondary" id="delete-item">Remove '+kind+'</button></div>');
 $('delete-item')?.addEventListener('click',async()=>{if(!confirm(`Remove this ${kind} from the app? This does not change the printer.`))return;try{await api(`${kind==='printer'?'printers':'spools'}/${editor.id}`,'DELETE');$('editor').close();await refresh();}catch(e){$('form-error').textContent=e.message;}});
 $('editor').showModal();
}
$('edit-form').addEventListener('submit',async e=>{
 e.preventDefault();const values=Object.fromEntries(new FormData(e.target));
 if(editor.kind==='spool'){values.initial_g=Number(values.initial_g);values.remaining_g=Number(values.remaining_g);values.printer_id=values.printer_id?Number(values.printer_id):null;}
 $('save').disabled=true;
 try{await api((editor.kind==='printer'?'printers':'spools')+(editor.id?'/'+editor.id:''),editor.id?'PUT':'POST',values);$('editor').close();await refresh();}catch(e){$('form-error').textContent=e.message;}finally{$('save').disabled=false;}
});
async function detail(id){
 detailId=id;const p=printers.find(p=>p.id===id),s=p.status;$('detail-title').textContent=p.name;
 $('detail-body').innerHTML=`<p>${esc(p.model)} · ${esc(s.firmware_version||'Firmware not reported')}</p>${p.camera!=='off'?'<img id="camera-image" class="camera" alt="Local printer camera"><p id="camera-message" class="subtle">Loading a camera snapshot…</p>':''}<h3>Reported alerts</h3>${(s.hms_errors||[]).map(e=>`<p class="error">${esc(e.full_code||e.code)} · ${esc(e.description||'Unrecognized printer alert')}</p>`).join('')||'<p>No alerts in the latest report.</p>'}<div id="extra-telemetry"></div><h3>Observed history</h3><p class="subtle">Recorded while this app is running. This is not the printer’s complete print history.</p><div id="history">Loading…</div>`;
 const temp=s.temperatures||{};const additional=Object.entries(temp).filter(([k])=>!k.startsWith('_')&&!['bed','nozzle','chamber','chamber_heating'].includes(k));
 $('extra-telemetry').innerHTML=(additional.length?'<h3>Additional temperature readings</h3>'+additional.map(([k,v])=>`<p class="subtle">${esc(k.replaceAll('_',' '))}: ${num(v,'°C')}</p>`).join(''):'')+(s.nozzle_rack?.length?'<h3>H2C nozzle rack</h3><pre id="rack"></pre>':'');
 if($('rack'))$('rack').textContent=JSON.stringify(s.nozzle_rack,null,2);
 $('detail').showModal();
 if(p.camera!=='off')loadCamera(id);
 try{const h=await api(`printers/${id}/history`);if(detailId!==id)return;
 const valid=h.samples.filter(x=>x.bed!==null);const points=valid.map((x,i)=>`${valid.length>1?i/(valid.length-1)*580:0},${110-Math.max(0,Math.min(120,x.bed))/120*100}`).join(' ');
 $('history').innerHTML=(valid.length>1?`<svg class="chart" viewBox="0 0 600 130" role="img" aria-label="Observed bed temperature over the latest two hours, scale 0 to 120 degrees Celsius"><polyline points="${points}" fill="none" stroke="#a3e6bd" stroke-width="2"/><text x="0" y="128" fill="#95a8a3" font-size="11">Bed temperature · latest 120 samples · 0–120°C</text></svg>`:'')+`<table class="history"><thead><tr><th>Observed</th><th>State</th><th>Print</th></tr></thead><tbody>${h.events.map(x=>`<tr><td>${esc(stamp(x.observed_at))}</td><td>${esc(x.state)}</td><td>${esc(x.name)}</td></tr>`).join('')}</tbody></table>`;
 }catch(e){if(detailId===id)$('history').textContent=e.message;}
}
async function loadCamera(id){
 if(detailId!==id)return;
 try{const res=await fetch(`/api/printers/${id}/camera`);if(!res.ok){const value=await res.json();throw Error(value.detail||'Camera unavailable');}const blob=await res.blob();if(detailId!==id)return;const img=$('camera-image');if(img.dataset.objectUrl)URL.revokeObjectURL(img.dataset.objectUrl);img.src=URL.createObjectURL(blob);img.dataset.objectUrl=img.src;$('camera-message').textContent='Snapshot updated '+new Date().toLocaleTimeString();cameraTimer=setTimeout(()=>loadCamera(id),10000);}
 catch(e){if(detailId===id){$('camera-message').textContent=e.message+' Close and reopen to retry.';}}
}
$('detail').addEventListener('close',()=>{detailId=null;clearTimeout(cameraTimer);const img=$('camera-image');if(img?.dataset.objectUrl)URL.revokeObjectURL(img.dataset.objectUrl);});
$('close-detail').onclick=()=>$('detail').close();$('close-editor').onclick=$('cancel-editor').onclick=()=>$('editor').close();
$('add-printer').onclick=()=>openEditor('printer');$('add-spool').onclick=()=>openEditor('spool');
for(const view of ['printers','filament'])$(view+'-tab').onclick=()=>{for(const other of ['printers','filament']){$(other+'-view').hidden=other!==view;$(other+'-tab').classList.toggle('selected',other===view);}};
$('printer-search').oninput=$('spool-search').oninput=render;
document.addEventListener('click',e=>{const b=e.target.closest('[data-action]');if(!b)return;const id=Number(b.dataset.id);if(b.dataset.action==='detail')detail(id);else if(b.dataset.action==='edit-printer')openEditor('printer',printers.find(p=>p.id===id));else if(b.dataset.action==='edit-spool')openEditor('spool',spools.find(s=>s.id===id));});
async function tick(){await refresh();pollTimer=setTimeout(tick,5000);}tick();
fetch('/health').then(r=>r.json()).then(h=>$('version').textContent=h.version).catch(()=>{});
