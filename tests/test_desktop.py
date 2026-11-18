import unittest
import tempfile
from datetime import datetime
from pathlib import Path
from array import array
from desktop.core import DailyLog, Segmenter, MODEL_BY_KEY, model_ready

class CoreTests(unittest.TestCase):
    def test_logs_follow_capture_date_not_decode_date(self):
        with tempfile.TemporaryDirectory() as d:
            log = DailyLog(Path(d))
            a = datetime(2026, 11, 18, 23, 59, 59)
            b = datetime(2026, 11, 19, 0, 0, 1)
            log.append(a, "First\n sentence")
            log.append(b, "Tomorrow")
            log.append(a, "Late decoder result")
            self.assertEqual((Path(d)/"2026-11-18.txt").read_text(), "[23:59:59] First sentence\n[23:59:59] Late decoder result\n")
            self.assertEqual((Path(d)/"2026-11-19.txt").read_text(), "[00:00:01] Tomorrow\n")

    def test_segments_are_bounded_and_silence_does_not_emit(self):
        segmenter = Segmenter()
        now = datetime(2026, 11, 18, 12)
        silence = array("f", [0]*320)
        loud = array("f", [0.1]*320)
        for _ in range(200):
            self.assertIsNone(segmenter.feed(silence, now))
        chunks = [out for _ in range(1200) if (out := segmenter.feed(loud, now))]
        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(all(len(out.samples) <= 160000 and out.when == now for out in chunks))
        self.assertIsNotNone(segmenter.flush())

    def test_blank_results_never_create_logs(self):
        with tempfile.TemporaryDirectory() as d:
            DailyLog(Path(d)).append(datetime.now(), " \n ")
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_partial_model_is_not_ready(self):
        with tempfile.TemporaryDirectory() as d:
            model = MODEL_BY_KEY["parakeet"]
            folder = Path(d)
            for file in model.files[:-1]:
                (folder/file).write_bytes(b"test")
            self.assertFalse(model_ready(folder, model))
            (folder/model.files[-1]).touch()
            self.assertFalse(model_ready(folder, model))
            (folder/model.files[-1]).write_bytes(b"ok")
            self.assertTrue(model_ready(folder, model))

if __name__ == "__main__":
    unittest.main()
