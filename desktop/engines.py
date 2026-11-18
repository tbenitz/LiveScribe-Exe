import os
from pathlib import Path

def open_engine(model, path):
    threads = min(6, max(1, (os.cpu_count() or 2) - 1))
    if model.key == "parakeet":
        import sherpa_onnx
        encoder, decoder, joiner, tokens = (str(path / f) for f in model.files)
        recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=encoder, decoder=decoder, joiner=joiner, tokens=tokens,
            model_type="nemo_transducer", num_threads=threads, provider="cpu",
        )
        def decode(samples, _language):
            stream = recognizer.create_stream()
            stream.accept_waveform(16000, samples)
            recognizer.decode_stream(stream)
            return stream.result.text
        return decode
    from faster_whisper import WhisperModel
    # Explicit local tokenizer and weight files are verified by the caller.
    recognizer = WhisperModel(str(Path(path).resolve()), device="cpu",
                              compute_type="int8", cpu_threads=threads, local_files_only=True)
    def decode(samples, language):
        segments, _ = recognizer.transcribe(samples, language=None if language == "auto" else language,
                                            beam_size=1, condition_on_previous_text=False,
                                            vad_filter=False, without_timestamps=True)
        return " ".join(s.text.strip() for s in segments)
    return decode
