import {MODELS} from './models.js';

let decode;
async function load(key, device) {
  const m = MODELS.find(x=>x.key === key);
  if (!m) throw new Error('Unknown model');
  if (m.key === 'parakeet') {
    const {fromUrls} = await import('parakeet.js');
    const base = 'https://huggingface.co/ysdede/parakeet-tdt-0.6b-v3-onnx/resolve/e5356bf6e24bdb7a269536b0e9e7869bc034b893';
    postMessage({type:'progress', text:'Downloading or opening Parakeet weights. First load can take several minutes.'});
    const model = await fromUrls({
      encoderUrl: base + (device === 'webgpu' ? '/encoder-model.fp16.onnx' : '/encoder-model.int8.onnx'),
      decoderUrl: base + '/decoder_joint-model.int8.onnx',
      tokenizerUrl: base + '/vocab.txt',
      preprocessorBackend:'js',
      backend:device,
      numThreads:1,
    });
    return async pcm => (await model.transcribe(pcm,16000,{returnTimestamps:false})).utterance_text;
  }
  const {pipeline,env} = await import('@huggingface/transformers');
  env.allowLocalModels = false;
  env.backends.onnx.wasm.numThreads = 1;
  const model = await pipeline('automatic-speech-recognition', m.repo, {
    revision:m.revision, device, dtype:m.dtype,
    progress_callback:({status,file,progress}) => {
      if (status==='progress' && Number.isFinite(progress)) postMessage({type:'progress', text:`Downloading ${file.split('/').at(-1)} · ${Math.floor(progress)}%`});
      if (status==='done') postMessage({type:'progress',text:'Preparing model…'});
    },
  });
  return async pcm => (await model(pcm,{return_timestamps:false,condition_on_prev_tokens:false})).text;
}

self.onmessage = async ({data}) => {
  const {type,id} = data;
  try {
    if (type==='load') {
      decode = await load(data.key,data.device);
      postMessage({type:'result',id});
    } else if (type==='decode') {
      if (!decode) throw new Error('Model has not loaded');
      postMessage({type:'result',id,text:await decode(data.pcm)});
    }
  } catch (err) {
    postMessage({type:'error',id,text:err?.message || String(err)});
  }
};
