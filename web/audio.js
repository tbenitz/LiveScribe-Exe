export const RATE = 16000;

export function resample(samples, from, to = RATE) {
  if (from === to) return samples;
  const size = Math.floor(samples.length * to / from), result = new Float32Array(size);
  for (let i = 0; i < size; i++) {
    const a = i * from / to, b = (i + 1) * from / to;
    let sum = 0;
    for (let j = Math.floor(a); j < b && j < samples.length; j++)
      sum += samples[j] * (Math.min(j + 1, b) - Math.max(j, a));
    result[i] = sum / (b - a);
  }
  return result;
}

export function localDay(date = new Date()) {
  return [date.getFullYear(), date.getMonth() + 1, date.getDate()].map(x => String(x).padStart(2,'0')).join('-');
}

export function timestamp(date = new Date()) {
  return [date.getHours(), date.getMinutes(), date.getSeconds()].map(x => String(x).padStart(2,'0')).join(':');
}

export class SpeechWindows {
  constructor(rate, emit) {
    this.rate = rate; this.emit = emit;
    this.preroll = []; this.pending = []; this.length = 0;
    this.voice = 0; this.quiet = 0; this.trigger = 0;
  }
  add(frame, now = new Date()) {
    let sum = 0;
    for (const x of frame) sum += x*x;
    const voiced = Math.sqrt(sum/frame.length) > .008;
    if (!this.length) {
      this.preroll.push(frame);
      if (this.preroll.length > 10) this.preroll.shift();
      this.trigger = voiced ? this.trigger+1 : 0;
      if (this.trigger < 3) return;
      this.pending = this.preroll;
      this.preroll = [];
      this.length = this.pending.reduce((sum,x)=>sum+x.length,0);
      this.voice = this.trigger*frame.length;
      this.start = now;
    } else {
      this.pending.push(frame); this.length += frame.length;
      if (voiced) this.voice += frame.length;
    }
    this.quiet = voiced ? 0 : this.quiet + frame.length;
    if (this.length >= this.rate*9 || this.quiet >= this.rate*.60) this.flush();
  }
  flush() {
    if (this.voice >= this.rate*.15) {
      const pcm = new Float32Array(this.length);
      let off = 0;
      for (const f of this.pending) { pcm.set(f,off); off += f.length; }
      this.emit(resample(pcm,this.rate),this.start);
    }
    this.preroll = []; this.pending = []; this.length = this.voice = this.quiet = this.trigger = 0;
  }
}
