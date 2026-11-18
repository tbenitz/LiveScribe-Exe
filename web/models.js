export const MODELS = [
  {key:'tiny', name:'Whisper Tiny', ram:'8 GB', detail:'Fastest • multilingual', repo:'Xenova/whisper-tiny', revision:'5332fcc35e32a33b86612b9a57a89be7906102b1', dtype:'q8'},
  {key:'base', name:'Whisper Base', ram:'8 GB', detail:'Balanced • multilingual', repo:'Xenova/whisper-base', revision:'64da57285918e20ea79ea5c88eed7197933abaa8', dtype:'q8'},
  {key:'small', name:'Whisper Small', ram:'8 GB', detail:'Higher accuracy • slower', repo:'Xenova/whisper-small', revision:'2d67713f236afa48a18992566e7647f6ca848e13', dtype:'q8'},
  {key:'parakeet', name:'NVIDIA Parakeet TDT 0.6B v3', ram:'16 GB', detail:'25 European languages • WebGPU FP16 or WASM INT8'},
  {key:'turbo', name:'Whisper large-v3-turbo', ram:'16 GB', detail:'Large model • WebGPU recommended', repo:'onnx-community/whisper-large-v3-turbo', revision:'360ebcde2559d60bb474678be3c1de9ef347d01a', dtype:'q4'},
];
