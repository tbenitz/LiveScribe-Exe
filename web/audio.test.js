import test from 'node:test';
import assert from 'node:assert/strict';
import {resample, localDay, SpeechWindows} from './audio.js';

test('48 kHz audio downmix keeps signal and duration', () => {
  assert.deepEqual([...resample(Float32Array.of(1,0,-1,1,1,1),48000)], [0,1]);
});
test('export date uses local calendar', () => {
  assert.equal(localDay(new Date(2026,10,18,23,59)), '2026-11-18');
});
test('silence never transcribes and stopping flushes speech', () => {
  const result = [], windows = new SpeechWindows(16000,(pcm,when)=>result.push([pcm,when]));
  const silence = new Float32Array(320), speech = silence.map(()=>.1), now = new Date();
  for(let i=0;i<100;i++) windows.add(silence,now);
  assert.equal(result.length,0);
  for(let i=0;i<25;i++) windows.add(speech,now);
  windows.flush();
  assert.equal(result.length,1);
  assert.equal(result[0][1],now);
  assert.ok(result[0][0].length >= 8000);
});
