class LiveScribeCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.size = Math.round(sampleRate * 0.02);
    this.buffer = new Float32Array(this.size);
    this.at = 0;
    this.port.onmessage = ({data}) => {
      if (data === 'stop') {
        if (this.at) {
          const tail = this.buffer.slice(0,this.at);
          this.port.postMessage(tail,[tail.buffer]);
        }
        this.port.postMessage('stopped');
      }
    };
  }
  process(inputs) {
    const input = inputs[0]?.[0];
    if (!input) return true;
    for (const value of input) {
      this.buffer[this.at++] = value;
      if (this.at === this.size) {
        this.port.postMessage(this.buffer,[this.buffer.buffer]);
        this.buffer = new Float32Array(this.size);
        this.at = 0;
      }
    }
    return true;
  }
}
registerProcessor('livescribe-capture', LiveScribeCapture);
