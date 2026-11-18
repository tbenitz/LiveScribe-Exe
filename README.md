# LiveScribe

Live microphone transcription that runs on your device. The Windows app keeps a daily text log. The web demo lets you compare the same model families and download a transcript.

- [Browser demo](https://tbenitz.github.io/LiveScribe-Exe/)
- [Windows downloads and offline model packs](https://github.com/tbenitz/LiveScribe-Exe/releases)
- [Build and deploy status](https://github.com/tbenitz/LiveScribe-Exe/actions)

## Install on an offline Windows PC

1. Download **LiveScribe-Setup-x64-Offline.exe** from Releases on a connected computer. Copy it to the target PC on a USB drive.
2. Run the installer on 64-bit Windows 10 or 11. Whisper Base and the speech runtimes are included. It does not need an account, API key, Python installation, or an internet connection.
3. Open LiveScribe. Once the microphone opens, LiveScribe shows **Transcription has started** and the tray icon turns green. The tray has Start/Stop, Show/hide live text, Settings, Open transcript folder, and Exit. Closing the main window hides it to the tray. To turn off the microphone, use **Stop transcription** or **Exit LiveScribe**.
4. For another model, download its optional ZIP from Releases on a connected computer. Copy it to the offline PC, extract it, select that model in Settings, then choose **Import unpacked model folder** and pick the extracted model folder. Save settings, then stop and restart transcription. The browser's model cache is not a Windows model pack.

Daily plain-text logs go to **%LOCALAPPDATA%\LiveScribe\Transcripts\YYYY-MM-DD.txt** by default. Each recognized line is timestamped in local time. The first speech recognized after midnight starts a new file. Hiding the live text does not stop logging. Only text is retained, not microphone audio. Capture is from the selected microphone (or another Windows recording device you select), not automatic Teams/Zoom/system-audio loopback. There is no automatic speaker labeling. Only transcribe conversations you have permission to record. The Windows installer is unsigned.

## Which model should I try?

| Model | RAM starting point | Why choose it |
| --- | --- | --- |
| Whisper Tiny | 8 GB | Quickest. Try it first on older hardware. |
| Whisper Base | 8 GB | Balanced default and included in the installer. |
| Whisper Small | 8 GB | Often improves accuracy, but takes longer. |
| NVIDIA Parakeet TDT 0.6B v3 | 16 GB | For 25 European languages. Windows uses the INT8 CPU release. The browser offers WebGPU FP16 or CPU/WASM INT8. |
| Whisper large-v3-turbo | 16 GB | Larger multilingual option. Windows uses CPU INT8 inference. WebGPU recommended for the browser. |

RAM tiers are recommendations, not guarantees or GPU VRAM requirements. For continuous speech, decode needs to keep up with the microphone. If the app flags dropped audio, switch to a smaller model. The Windows and browser builds use different model conversions and can produce slightly different text.

## Browser demo

Open the HTTPS demo on a recent desktop version of Chrome or Edge. Pick a model and click **Try sample**, **Open audio**, or **Start microphone**. Audio and text are processed locally. The first model load needs the network to fetch public weights. Large weights may take several minutes, and browser storage can evict cached assets. Live text arrives in chunks after short pauses and periodically during uninterrupted speech. Use **Save TXT** before closing the tab.

## Build from source

- Browser: `cd web`, `npm ci --ignore-scripts`, `npm test`, `npm run dev` (development) or `npm run build` (static output in `web/dist`).
- Windows developer install: Python 3.12 x64, `python -m pip install -r desktop/requirements.txt`, then `python tools/fetch_model.py base --root models` and `python -m desktop.app`. Runtime works from locally staged files only.
- The Windows Actions workflow compiles the app, tests bundled inference, creates the offline installer, and attaches it with the model packs to a release. The Pages workflow builds the static demo. In **Settings → Pages**, set Source to **GitHub Actions** for deployment.
- Tests: `python -m unittest discover -s tests -v` and `npm --prefix web test`.

Models: [NVIDIA Parakeet v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3), [sherpa-onnx](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/offline-transducer/nemo-transducer-models.html), [OpenAI Whisper](https://github.com/openai/whisper), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), and [parakeet.js](https://www.npmjs.com/package/parakeet.js). Model packs identify their original releases and conversion sources. The browser's bundled audio example is synthetic speech generated with Flite.
