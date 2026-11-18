# LiveScribe build plan

Build a Windows x64 microphone transcriber and a separately deployable GitHub Pages demo. Both offer Parakeet v3, Whisper large-v3-turbo, and smaller Whisper models. Use the system microphone by default, with an optional input selector. Start automatically on launch when the selected model is installed, and show a notice only after opening the microphone. Do not start with Windows by default. The tray can hide the live transcript without pausing capture, stop/start, open settings/logs, and exit. Do not record audio to disk or claim speaker identification or system-audio loopback.

1. Test speech segmentation, resource bounds, local-date log rotation, and model-pack readiness before desktop implementation.
2. Implement CPU transcription with faster-whisper and sherpa-onnx using explicit local paths. Package an installer with Whisper Base; make any other model available as a USB-transferable pack and add a local-only model import path.
3. Implement the GitHub Pages demo with browser inference, sample and microphone input, TXT export, and clear backend and memory labels. Keep model files out of git.
4. Verify the app logic, build the demo, smoke-test actual inference where the environment supports it, then run the Windows installer build and Pages deployment.
