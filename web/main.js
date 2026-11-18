import './style.css';
import {MODELS} from './models.js';
import {resample, localDay, timestamp, SpeechWindows} from './audio.js';
import captureUrl from './capture-worklet.js?url';
import sampleUrl from './sample.wav?url';

const $ = id => document.getElementById(id);
const [start,stop,audio,sample,save,clear,visible,backend,file,status,indicator,transcript,lines,empty,models] =
  ['start','stop','audio','sample','save','clear','visible','backend','file','status','indicator','transcript','lines','empty','models'].map($);
for (const model of MODELS) {
  const label = document.createElement('label');
  label.className='model';
  label.innerHTML = `<input type="radio" name="model" value="${model.key}" ${model.key==='base'?'checked':''}><span>${model.name}</span><b>${model.ram} RAM</b><small>${model.detail}</small>`;
  models.append(label);
}
let rows = [], worker, loaded, index = 0, pending = new Map(), session = null;
function say(text) { status.textContent=text; }
function ui() {
  const active=!!session;
  for (const el of [start,audio,sample,backend,...models.querySelectorAll('input')]) el.disabled=active;
  stop.disabled=!active || session.stopping;
  save.disabled=clear.disabled=!rows.length;
  indicator.textContent=session?.micLive?'MIC ON':'MIC OFF';
  indicator.classList.toggle('live',!!session?.micLive);
}
function closeWorker(error = new Error('Cancelled')) {
  worker?.terminate(); worker=null; loaded=null;
  for (const value of pending.values()) value.reject(error);
  pending = new Map();
}
function rpc(type,payload={},transfer=[]) {
  return new Promise((resolve,reject)=>{
    const id = ++index;
    pending.set(id,{resolve,reject});
    worker.postMessage({type,id,...payload},transfer);
  });
}
function openWorker() {
  worker = new Worker(new URL('./inference-worker.js',import.meta.url),{type:'module'});
  worker.onmessage = ({data}) => {
    if (data.type==='progress') { if (session && !session.stopping) say(data.text); return; }
    const p=pending.get(data.id);
    if (!p) return;
    pending.delete(data.id);
    data.type==='error'?p.reject(new Error(data.text)):p.resolve(data);
  };
  worker.onerror = e => closeWorker(new Error(e.message || 'The model worker crashed.'));
}
async function modelFor(run) {
  const key=models.querySelector(':checked').value;
  const selectedBackend=backend.value;
  const gpu=selectedBackend!=='wasm' && (key==='parakeet' || key==='turbo' || selectedBackend==='webgpu') &&
    (await navigator.gpu?.requestAdapter().catch(()=>null));
  if (session!==run) throw new Error('Cancelled');
  if (selectedBackend==='webgpu' && !gpu) throw new Error('WebGPU is unavailable. Select CPU / WASM.');
  const candidates=gpu ? (selectedBackend==='auto'?['webgpu','wasm']:['webgpu']) : ['wasm'];
  let last;
  for (const device of candidates) {
    const id=key+'|'+device;
    if (loaded === id && worker) return device;
    closeWorker();
    openWorker();
    say(`Loading ${MODELS.find(m=>m.key===key).name} on ${device==='wasm'?'CPU / WASM':'WebGPU'}…`);
    try { await rpc('load',{key,device}); loaded=id; return device; }
    catch(e) { last=e; closeWorker(); if (session!==run) throw e; }
  }
  throw last;
}
function add(text,when) {
  text=(text||'').replace(/\s+/g,' ').trim();
  if (!text) return;
  rows.push({text,when});
  const row=document.createElement('li'), time=document.createElement('time'), words=document.createElement('span');
  time.textContent=typeof when==='string'?when:timestamp(when);
  words.textContent=text;
  row.append(time,words); lines.append(row);
  if (lines.childElementCount>500) lines.firstElementChild.remove();
  empty.hidden=true; transcript.scrollTop=transcript.scrollHeight;
  ui();
}
async function infer(pcm) { return (await rpc('decode',{pcm},[pcm.buffer])).text; }
function enqueue(run,pcm,when) {
  if (session!==run) return;
  if (run.waiting>=6) { run.dropped=true; say('Model is behind. Some audio was skipped. Try a smaller model.'); return; }
  run.waiting++;
  run.tail=run.tail.then(async()=>{
    if (session!==run) return;
    add(await infer(pcm),when);
  }).catch(e=>{ if(session===run) { run.failure=e; void stopMic(run); } }).finally(()=>run.waiting--);
}
function begin(kind) {
  if (session) return null;
  const run=session={kind,stopping:false,micLive:false,waiting:0,tail:Promise.resolve()};
  ui(); return run;
}
function finish(run,text) {
  if (session!==run) return;
  session=null; say(text); ui();
}
async function stopMic(run) {
  if (run.stopping) return;
  run.stopping=true; run.micLive=false; ui();
  if (!run.node) { closeWorker(); run.stream?.getTracks().forEach(t=>t.stop()); finish(run,'Stopped · microphone off.'); return; }
  say('Stopped listening. Finishing queued speech…');
  if (!run.failure) {
    await new Promise(resolve=>{
      const timeout=setTimeout(resolve,250);
      run.ack=()=>{clearTimeout(timeout);resolve();};
      run.node.port.postMessage('stop');
    });
    run.windows.flush();
  }
  run.stream.getTracks().forEach(t=>t.stop());
  await run.context.close().catch(()=>{});
  await run.tail;
  if(run.failure) closeWorker();
  finish(run,run.failure?`Transcription stopped · ${run.failure.message}. Try a smaller model or switch backend.`:
    run.dropped?'Stopped · some audio was skipped.':'Stopped · microphone off.');
}

start.onclick=async()=>{
  if(!navigator.mediaDevices?.getUserMedia) { say('Microphone access requires HTTPS or localhost.'); return; }
  const run=begin('mic'); if(!run) return;
  try {
    const device=await modelFor(run);
    if(session!==run) return;
    say('Waiting for microphone permission…');
    run.stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1}});
    if(session!==run) { run.stream.getTracks().forEach(t=>t.stop()); return; }
    run.context=new AudioContext();
    await run.context.audioWorklet.addModule(captureUrl);
    if(session!==run) { await run.context.close().catch(()=>{}); return; }
    run.node=new AudioWorkletNode(run.context,'livescribe-capture');
    run.windows=new SpeechWindows(run.context.sampleRate,(pcm,when)=>enqueue(run,pcm,when));
    run.node.port.onmessage=({data})=>{
      if(data==='stopped') run.ack?.();
      else run.windows.add(data);
    };
    const muted=run.context.createGain(); muted.gain.value=0;
    run.context.createMediaStreamSource(run.stream).connect(run.node).connect(muted).connect(run.context.destination);
    await run.context.resume();
    if(session!==run || run.stopping) return;
    run.micLive=true;
    run.stream.getTracks().forEach(track=>track.onended=()=>void stopMic(run));
    say(`Transcription has started · ${device==='wasm'?'CPU / WASM':'WebGPU'}.`); ui();
  } catch(e) {
    run.stream?.getTracks().forEach(t=>t.stop());
    await run.context?.close().catch(()=>{});
    finish(run,`Could not start · ${e.message}`);
  }
};

async function transcribeFile(getBytes) {
  const run=begin('file'); if(!run) return;
  try {
    await modelFor(run);
    if(session!==run) return;
    say('Decoding audio locally…');
    const context=new AudioContext();
    let decoded;
    try { decoded=await context.decodeAudioData(await getBytes()); }
    finally { await context.close().catch(()=>{}); }
    const win=9*decoded.sampleRate;
    for(let at=0;at<decoded.length && session===run;at+=win) {
      const count=Math.min(win,decoded.length-at), mono=new Float32Array(count);
      for(let ch=0;ch<decoded.numberOfChannels;ch++) {
        const data=decoded.getChannelData(ch);
        for(let i=0;i<count;i++) mono[i]+=data[at+i]/decoded.numberOfChannels;
      }
      let sum=0; for(const x of mono) sum+=x*x;
      say(`Transcribing audio · ${Math.floor(at/decoded.length*100)}%`);
      if(Math.sqrt(sum/count)>.001) {
        const text=await infer(resample(mono,decoded.sampleRate));
        const seconds=Math.floor(at/decoded.sampleRate);
        const format=n=>String(n).padStart(2,'0');
        add(text,`${format(Math.floor(seconds/3600))}:${format(Math.floor(seconds/60)%60)}:${format(seconds%60)}`);
      }
    }
    finish(run,'Audio finished · 100%.');
  } catch(e) { finish(run,`Could not transcribe audio · ${e.message}`); }
}
stop.onclick=()=>{
  const run=session; if(!run) return;
  if(run.kind==='mic') void stopMic(run);
  else { closeWorker(); finish(run,'Stopped. Finished text was kept.'); }
};
audio.onclick=()=>file.click();
file.onchange=()=>{ const f=file.files[0]; file.value=''; if(f) void transcribeFile(()=>f.arrayBuffer()); };
sample.onclick=()=>void transcribeFile(async()=>{
  const r=await fetch(sampleUrl);
  if(!r.ok) throw new Error('Sample audio could not load.');
  return r.arrayBuffer();
});
visible.onchange=()=>{transcript.hidden=!visible.checked;};
clear.onclick=()=>{ rows=[]; lines.replaceChildren(); empty.hidden=false; ui(); };
save.onclick=()=>{
  const blob=new Blob([rows.map(({text,when})=>`[${typeof when==='string'?when:timestamp(when)}] ${text}`).join('\n')+'\n'],{type:'text/plain;charset=utf-8'});
  const url=URL.createObjectURL(blob), link=document.createElement('a');
  link.href=url; link.download=`LiveScribe-${localDay()}.txt`; link.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
};
ui();
