"""Model catalog, speech segmentation and local-date transcript persistence."""
from array import array
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import math

RATE = 16000
FRAME = 320
CT2 = ("config.json", "model.bin", "tokenizer.json", "vocabulary.json")

@dataclass(frozen=True)
class Model:
    key: str
    name: str
    tier: int
    files: tuple[str, ...]
    repo: str = ""

MODELS = (
    Model("tiny", "Whisper Tiny · fastest", 8, CT2[:-1] + ("vocabulary.txt",), "Systran/faster-whisper-tiny"),
    Model("base", "Whisper Base · included", 8, CT2[:-1] + ("vocabulary.txt",), "Systran/faster-whisper-base"),
    Model("small", "Whisper Small · more accurate", 8, CT2[:-1] + ("vocabulary.txt",), "Systran/faster-whisper-small"),
    Model("parakeet", "NVIDIA Parakeet TDT 0.6B v3", 16, ("encoder.int8.onnx", "decoder.int8.onnx", "joiner.int8.onnx", "tokens.txt")),
    Model("turbo", "Whisper large-v3-turbo", 16, CT2, "mobiuslabsgmbh/faster-whisper-large-v3-turbo"),
)
MODEL_BY_KEY = {m.key: m for m in MODELS}

def model_ready(folder: Path, model: Model) -> bool:
    return all((folder / f).is_file() and (folder / f).stat().st_size > 0 for f in model.files)

class DailyLog:
    def __init__(self, folder):
        self.folder = folder

    def append(self, when, text):
        text = " ".join(text.split())
        if not text:
            return
        self.folder.mkdir(parents=True, exist_ok=True)
        with (self.folder / f"{when:%Y-%m-%d}.txt").open("a", encoding="utf-8", newline="\n") as f:
            f.write(f"[{when:%H:%M:%S}] {text}\n")

@dataclass
class Chunk:
    when: datetime
    samples: array

class Segmenter:
    def __init__(self, threshold=0.008):
        self.threshold = threshold
        self.history = deque(maxlen=12)
        self.buffer = array("f")
        self.when = None
        self.quiet = self.voiced = self.trigger = 0

    def feed(self, frame, when):
        # A date boundary always closes the old segment, even on continuous speech.
        previous = None
        if self.when and when.date() != self.when.date():
            previous = self.flush()
        if self.history and self.history[-1][1].date() != when.date():
            self.history.clear()
            self.trigger = 0
        voiced = math.sqrt(sum(s*s for s in frame)/len(frame)) >= self.threshold
        if self.when is None:
            self.history.append((frame, when))
            self.trigger = self.trigger + 1 if voiced else 0
            if self.trigger < 3:
                return previous
            self.when = when
            self.voiced = self.trigger
            for samples, _ in self.history:
                self.buffer.extend(samples)
            self.history.clear()
        else:
            self.buffer.extend(frame)
            self.voiced += int(voiced)
        self.quiet = 0 if voiced else self.quiet + 1
        if self.quiet >= 30 or len(self.buffer) >= RATE * 10:
            return self.flush()
        return previous

    def flush(self):
        chunk = Chunk(self.when, self.buffer) if self.when and self.voiced >= 8 else None
        self.buffer = array("f")
        self.history.clear()
        self.quiet = self.voiced = self.trigger = 0
        self.when = None
        return chunk
