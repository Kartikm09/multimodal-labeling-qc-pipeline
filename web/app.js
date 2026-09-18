'use strict';
const $ = id => document.getElementById(id);
let documentValue, current, original, sequence = 0;
const status = text => { $('status').textContent = text; };
async function request(path, payload) {
  const response = await fetch(path, payload ? {method:'POST', headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)} : {});
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || 'Request failed');
  return body;
}
function option(value, text) { const node=document.createElement('option'); node.value=value;node.textContent=text;return node; }
function seconds(tick) { return tick * documentValue.media.timebase[0] / documentValue.media.timebase[1]; }
function eventFields() {
  const event=documentValue?.events[Number($('event').value)];
  if(!event){$('review').querySelectorAll('input,select,textarea,button').forEach(control=>control.disabled=true);return;}
  for(const field of ['action','outcome','start','end','actor','object','uncertainty','overlap_group','overlap_reason']) $(field).value=event[field];
  for(const field of ['partial','occluded']) $(field).checked=event[field];
}
function timeDisplay() {
  if(!documentValue)return;
  const tick=Math.round($('clip').currentTime/documentValue.media.timebase[0]*documentValue.media.timebase[1]);
  let index=0;documentValue.media.pts.forEach((pts,i)=>{if(pts<=tick)index=i;});
  $('time').textContent=`Frame ${index} · ${$('clip').currentTime.toFixed(3)} s · PTS ${documentValue.media.pts[index]}`;
}
function step(direction) {
  if(!documentValue)return;
  $('clip').pause();
  const pts=documentValue.media.pts;const tick=Math.round($('clip').currentTime/documentValue.media.timebase[0]*documentValue.media.timebase[1]);
  let index=0;pts.forEach((p,i)=>{if(p<=tick)index=i;});
  index=Math.min(pts.length-1,Math.max(0,index+direction));$('clip').currentTime=seconds(pts[index]);timeDisplay();
}
async function loadCase(preserveMedia=false) {
  const token=++sequence;const id=$('case').value;status('Loading local case…');
  const controls=document.querySelectorAll('form input,form select,form textarea,form button,#event');controls.forEach(control=>control.disabled=true);documentValue=undefined;
  try {
    const data=await request(`/api/cases/${id}`);if(token!==sequence)return;
    current=data.history.at(-1);documentValue=structuredClone(current.document);original=data.history[0].document;
    $('revision').textContent=`Revision ${current.revision} · timebase ${documentValue.media.timebase.join('/')} s`;
    if(!preserveMedia){$('clip').src=`/media/${id}.mp4`;$('clip').load();}
    $('json').href=`/api/cases/${id}/export.json`;$('xml').href=`/api/cases/${id}/export.xml`;
    $('event').replaceChildren(...documentValue.events.map((event,i)=>option(i,`${event.id} · ${event.action}`)));
    if(!documentValue.events.length)$('event').append(option('', 'No events in this revision'));
    const table=document.createElement('table');const head=table.createTHead().insertRow();
    for(const name of ['Event','Original (s)','Latest (s)','Outcome']){const th=document.createElement('th');th.textContent=name;head.append(th);}
    const body=table.createTBody();for(const event of documentValue.events){const before=original.events.find(x=>x.id===event.id);const row=body.insertRow();for(const text of [event.action,before ? `${seconds(before.start).toFixed(2)}–${seconds(before.end).toFixed(2)}` : 'Added in review',`${seconds(event.start).toFixed(2)}–${seconds(event.end).toFixed(2)}`,event.outcome])row.insertCell().textContent=text;}
    if(!documentValue.events.length){const empty=document.createElement('p');empty.textContent='No events in this revision. Original labels remain in review history and the JSON export history API.';$('comparison').replaceChildren(empty);}else $('comparison').replaceChildren(table);
    $('history').replaceChildren(...data.history.map(revision=>{const li=document.createElement('li');li.textContent=`Revision ${revision.revision} · ${revision.reviewer} · ${revision.reason}`;return li;}));
    for(const side of ['left','right'])$(side).replaceChildren(...data.history.map(revision=>option(revision.revision,`Revision ${revision.revision}`)));
    $('right').value=current.revision;
    $('rankings').replaceChildren(...data.rankings.map(rank=>{const li=document.createElement('li');li.textContent=`${rank.left_revision} vs ${rank.right_revision}: ${rank.preference}. ${rank.evidence}`;return li;}));
    controls.forEach(control=>control.disabled=false);eventFields();
    status('Ready. All clips and original labels are synthetic. Reviewer changes remain separate.');timeDisplay();
  } catch(error){if(token===sequence)status(error.message);}
}
$('review').addEventListener('submit',async event=>{
  event.preventDefault();const edited=structuredClone(documentValue);const row=edited.events[Number($('event').value)];
  for(const field of ['action','outcome','actor','object','uncertainty','overlap_group','overlap_reason'])row[field]=$(field).value;
  for(const field of ['start','end'])row[field]=Number($(field).value);
  for(const field of ['partial','occluded'])row[field]=$(field).checked;
  const caseId=edited.id;const token=sequence;
  try{await request(`/api/cases/${caseId}/revisions`,{document:edited,reviewer:$('reviewer').value,reason:$('reason').value,expected_revision:current.revision});if(token!==sequence)return;await loadCase(true);status('Saved a new revision. The original labels are preserved.');$('reason').value='';$('event').focus();}
  catch(error){if(token===sequence)status(error.message);}
});
$('ranking').addEventListener('submit',async event=>{event.preventDefault();const id=documentValue.id;const token=sequence;try{await request(`/api/cases/${id}/rankings`,{left:Number($('left').value),right:Number($('right').value),preference:$('preference').value,evidence:$('ranking_evidence').value});if(token!==sequence)return;await loadCase(true);status('Pairwise ranking saved with written evidence.');$('ranking_evidence').value='';}catch(error){if(token===sequence)status(error.message);}});
$('case').addEventListener('change',()=>loadCase());$('event').addEventListener('change',eventFields);$('clip').addEventListener('timeupdate',timeDisplay);$('previous').addEventListener('click',()=>step(-1));$('next').addEventListener('click',()=>step(1));loadCase();
