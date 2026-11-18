"""Windows microphone, tray and transcript interface."""
import ctypes
import json
import queue
import os
import sys
import shutil
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from array import array
from collections import deque

import numpy as np
import sounddevice as sd
import pystray
from PIL import Image, ImageDraw

from desktop.core import MODELS, MODEL_BY_KEY, model_ready, DailyLog, Segmenter, RATE, FRAME
from desktop.engines import open_engine

APP = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "LiveScribe"
RES = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
LOCAL_MODELS = APP / "models"
DEFAULTS = {"model": "base", "visible": True, "launch": True, "device": "Default microphone",
            "language": "auto", "threshold": "0.008", "log": str(APP / "Transcripts")}
COLORS = {"idle": "#46647b", "live": "#007f65"}

def icon(active=False):
    im = Image.new("RGBA", (64,64))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0,0,63,63), radius=16, fill=COLORS["live" if active else "idle"])
    for x, height in [(14,14),(23,26),(32,38),(41,26),(50,14)]:
        d.rounded_rectangle((x-2,32-height//2,x+2,32+height//2), radius=2, fill="white")
    return im

@dataclass
class Capture:
    config: dict
    stop: threading.Event = field(default_factory=threading.Event)
    audio: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=500))
    chunks: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=6))
    skipped: threading.Event = field(default_factory=threading.Event)
    ready: bool = False

class App:
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.current = None
        self.importing = False
        self.quitting = False
        self.rows = deque(maxlen=500)
        self.config = DEFAULTS.copy()
        try:
            data = json.loads((APP / "settings.json").read_text(encoding="utf-8"))
            self.config.update({key: value for key, value in data.items() if key in DEFAULTS and isinstance(value, type(DEFAULTS[key]))})
        except (OSError, ValueError, AttributeError):
            pass
        if self.config["model"] not in MODEL_BY_KEY:
            self.config["model"] = "base"
        root.title("LiveScribe")
        root.geometry("760x530")
        root.minsize(610, 420)
        root.protocol("WM_DELETE_WINDOW", root.withdraw)
        frame = ttk.Frame(root, padding=20)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="LiveScribe", font=("Segoe UI", 24, "bold")).pack(anchor="w")
        self.status = tk.StringVar(value="Stopped · microphone off")
        ttk.Label(frame, textvariable=self.status, wraplength=620).pack(anchor="w", pady=(4,12))
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")
        self.start_button = ttk.Button(buttons, text="Start transcription", command=self.toggle)
        self.start_button.pack(side="left")
        for label, f in [("Settings",self.settings),("Open logs",self.open_logs),("Hide to tray",root.withdraw)]:
            ttk.Button(buttons,text=label,command=f).pack(side="left", padx=4)
        self.visible = tk.BooleanVar(value=self.config["visible"])
        ttk.Checkbutton(frame,text="Show live transcript",variable=self.visible,command=self.show_change).pack(anchor="w",pady=12)
        self.transcript = tk.Text(frame, wrap="word", state="disabled", bg="#f1f5f9",
                                  foreground="#17314a", font=("Segoe UI",11), relief="flat",padx=12,pady=12)
        self.scrollbar = ttk.Scrollbar(frame, command=self.transcript.yview)
        self.transcript.configure(yscrollcommand=self.scrollbar.set)
        self.paint()
        self.tray = pystray.Icon("LiveScribe", icon(), "LiveScribe · microphone off",
                  pystray.Menu(
                      pystray.MenuItem("Open LiveScribe", lambda: self.events.put(("action", self.show)), default=True),
                      pystray.MenuItem(lambda _: "Stop transcription" if self.current else "Start transcription",
                                       lambda: self.events.put(("action",self.toggle))),
                      pystray.MenuItem("Show / hide live text", lambda: self.events.put(("action",self.toggle_text))),
                      pystray.MenuItem("Settings", lambda: self.events.put(("action",self.settings))),
                      pystray.MenuItem("Open transcript folder", lambda: self.events.put(("action",self.open_logs))),
                      pystray.MenuItem("Exit LiveScribe", lambda: self.events.put(("action",self.exit))),
                  ))
        self.tray.run_detached()
        root.after(60,self.poll)
        if self.config["launch"]:
            root.after(350,self.start)

    def show(self):
        self.root.deiconify()
        self.root.lift()

    def save(self):
        APP.mkdir(parents=True,exist_ok=True)
        tmp = APP / "settings.tmp"
        tmp.write_text(json.dumps(self.config, indent=2), encoding="utf-8")
        tmp.replace(APP / "settings.json")

    def show_change(self):
        self.config["visible"] = self.visible.get()
        self.save()
        self.paint()

    def toggle_text(self):
        self.visible.set(not self.visible.get())
        self.show_change()
        if self.visible.get():
            self.show()

    def paint(self):
        if not self.visible.get():
            self.transcript.pack_forget()
            self.scrollbar.pack_forget()
            return
        self.scrollbar.pack(side="right", fill="y")
        self.transcript.pack(side="left", fill="both", expand=True)
        self.transcript.configure(state="normal")
        self.transcript.delete("1.0","end")
        self.transcript.insert("end", "\n".join(self.rows) or "Recognized speech will appear here.")
        self.transcript.configure(state="disabled")
        self.transcript.see("end")

    def open_logs(self):
        try:
            folder = Path(self.config["log"])
            folder.mkdir(parents=True,exist_ok=True)
            os.startfile(folder)
        except OSError as exc:
            messagebox.showerror("Cannot open folder", str(exc))

    def model_path(self, model):
        for parent in (LOCAL_MODELS, RES / "models"):
            path = parent / model.key
            if model_ready(path, model):
                return path
        return None

    def settings(self):
        self.show()
        existing = getattr(self, "settings_window", None)
        if existing and existing.winfo_exists():
            existing.lift()
            return
        w = self.settings_window = tk.Toplevel(self.root)
        w.title("LiveScribe settings")
        w.resizable(False, False)
        f = ttk.Frame(w,padding=18)
        f.pack(fill="both")
        variables = {k:tk.StringVar(value=v) for k,v in self.config.items() if isinstance(v,str)}
        labels = {m.key:f"{m.tier} GB RAM guide · {m.name}" for m in MODELS}
        variables["model"].set(labels[self.config["model"]])
        device_names = ["Default microphone"]
        try:
            for i, device in enumerate(sd.query_devices()):
                if device["max_input_channels"]:
                    api = sd.query_hostapis(device["hostapi"])["name"]
                    device_names.append(f"{i} · {device['name']} ({api})")
        except sd.PortAudioError:
            pass
        for field_name,label,opts in [
            ("model","Speech model",list(labels.values())),
            ("device","Microphone",device_names),
            ("language","Whisper language",["auto","en","es","fr","de","it","pt","ja","zh","ar","hi","ru"]),
            ("threshold","Microphone sensitivity",["0.003","0.005","0.008","0.012","0.020"]),
            ("log","Transcript folder",None),
        ]:
            row=f.grid_size()[1]
            ttk.Label(f,text=label).grid(row=row,column=0,sticky="w",pady=5)
            widget = ttk.Combobox(f,width=52, textvariable=variables[field_name], values=opts, state="readonly") if opts else ttk.Entry(f,width=55,textvariable=variables[field_name])
            widget.grid(row=row,column=1,sticky="ew",padx=(10,0))
        def browse():
            path = filedialog.askdirectory(parent=w)
            if path:
                variables["log"].set(path)
        ttk.Button(f,text="Browse",command=browse).grid(row=4,column=2,padx=8)
        launch = tk.BooleanVar(value=self.config["launch"])
        ttk.Checkbutton(f,text="Start transcribing when I open LiveScribe",variable=launch).grid(row=5,columnspan=3,sticky="w",pady=8)
        model_status = tk.StringVar()
        def current_model():
            return next(m for m in MODELS if labels[m.key] == variables["model"].get())
        def refresh(*_):
            m = current_model()
            model_status.set(("Installed locally" if self.model_path(m) else "Not installed. Import this model's folder below.") +
                             f" · {m.tier} GB is a guide, not a hardware guarantee.")
        variables["model"].trace_add("write",refresh)
        refresh()
        ttk.Label(f,textvariable=model_status,wraplength=540).grid(row=6,columnspan=3,sticky="w",pady=6)
        import_btn = ttk.Button(f,text="Import unpacked model folder")
        def do_import():
            m=current_model()
            selected=filedialog.askdirectory(parent=w,title="Select the unpacked model folder")
            if not selected:
                return
            if not model_ready(Path(selected),m):
                messagebox.showerror("Incomplete model", "The folder needs: " + ", ".join(m.files),parent=w)
                return
            self.importing = True
            import_btn.configure(state="disabled")
            model_status.set("Copying model files. This can take a moment.")
            def copy():
                target=LOCAL_MODELS/m.key
                temp=LOCAL_MODELS/(m.key+".import")
                err=None
                try:
                    if Path(selected).resolve() != target.resolve():
                        if target.exists():
                            raise ValueError("This model already exists in " + str(target) + ". Move that folder out first to replace it.")
                        LOCAL_MODELS.mkdir(parents=True,exist_ok=True)
                        if temp.exists():
                            shutil.rmtree(temp)
                        temp.mkdir()
                        for name in (*m.files,"preprocessor_config.json","MODEL-SOURCE.txt"):
                            if (Path(selected)/name).is_file():
                                shutil.copyfile(Path(selected)/name,temp/name)
                        temp.rename(target)
                except (OSError,ValueError) as exc:
                    err = str(exc)
                def finished():
                    self.importing=False
                    if w.winfo_exists():
                        import_btn.configure(state="normal")
                        refresh()
                    if err:
                        messagebox.showerror("Model import failed",err)
                self.events.put(("action",finished))
            threading.Thread(target=copy,daemon=True).start()
        import_btn.configure(command=do_import,state="disabled" if self.importing else "normal")
        import_btn.grid(row=7,columnspan=3,sticky="w",pady=5)
        ttk.Label(f,text="A smaller sensitivity number picks up quieter speech. Model and audio changes apply on the next start.",wraplength=510).grid(row=8,columnspan=3,sticky="w",pady=5)
        def apply():
            if not variables["log"].get().strip():
                messagebox.showerror("Transcript folder", "Choose a transcript folder.",parent=w)
                return
            self.config.update({k:v.get() for k,v in variables.items()})
            self.config["model"]=current_model().key
            self.config["launch"]=launch.get()
            self.save()
            w.destroy()
        ttk.Button(f,text="Save settings",command=apply).grid(row=9,columnspan=3,sticky="e",pady=10)

    def toggle(self):
        if self.current:
            self.current.stop.set()
            self.status.set("Stopping · saving queued speech")
            self.start_button.configure(state="disabled")
        else:
            self.start()

    def start(self):
        if self.current or self.quitting:
            return
        model = MODEL_BY_KEY[self.config["model"]]
        path = self.model_path(model)
        if path is None:
            self.status.set(f"{model.name} is not installed. Import its model pack in Settings.")
            self.settings()
            return
        run = self.current = Capture(self.config.copy())
        self.status.set(f"Loading {model.name} · microphone off")
        self.start_button.configure(text="Stop",state="normal")
        self.tray.update_menu()
        threading.Thread(target=self.capture,args=(run,model,path),daemon=True).start()

    def capture(self,run,model,path):
        def report(kind,data=None):
            self.events.put((kind,run,data))
        def mic_callback(indata,_frames,_time,status):
            if run.stop.is_set():
                return
            if status:
                run.skipped.set()
            try:
                run.audio.put_nowait((bytes(indata),datetime.now()))
            except queue.Full:
                run.skipped.set()
        def segment():
            s=Segmenter(float(run.config["threshold"]))
            while True:
                item=run.audio.get()
                if item is None:
                    final=s.flush()
                    if final:
                        run.chunks.put(final)
                    run.chunks.put(None)
                    break
                raw,when=item
                frame=array("f")
                frame.frombytes(raw)
                chunk=s.feed(frame,when)
                if chunk:
                    try:
                        run.chunks.put_nowait(chunk)
                    except queue.Full:
                        run.skipped.set()
        errors=[]
        def decode():
            log=DailyLog(Path(run.config["log"]))
            while True:
                chunk=run.chunks.get()
                if chunk is None:
                    break
                if errors:
                    continue
                try:
                    text=infer(np.frombuffer(chunk.samples,dtype=np.float32),run.config["language"]).strip()
                    if text:
                        log.append(chunk.when,text)
                        report("line",f"[{chunk.when:%H:%M:%S}] " + " ".join(text.split()))
                except Exception as exc:
                    errors.append(exc)
                    run.stop.set()
        try:
            infer=open_engine(model,path)
            if run.stop.is_set():
                return
            device=None if run.config["device"]=="Default microphone" else int(run.config["device"].split(" · ")[0])
            with sd.RawInputStream(samplerate=RATE,blocksize=FRAME,device=device,channels=1,
                                   dtype="float32",callback=mic_callback):
                st=threading.Thread(target=segment,daemon=True)
                dt=threading.Thread(target=decode,daemon=True)
                st.start()
                dt.start()
                report("live",model.name)
                run.stop.wait()
            run.audio.put(None)
            st.join()
            dt.join()
            if errors:
                raise errors[0]
        except Exception as exc:
            report("error",str(exc))
        finally:
            report("finish")

    def poll(self):
        while True:
            try:
                event=self.events.get_nowait()
            except queue.Empty:
                break
            if event[0]=="action":
                event[1]()
                continue
            kind,run,data=event
            if run is not self.current:
                continue
            if kind=="live" and not run.stop.is_set():
                run.ready=True
                self.status.set(f"Listening · {data}")
                self.tray.icon=icon(True)
                self.tray.title="LiveScribe · microphone active"
                try:
                    self.tray.notify("Transcription has started. Your microphone is listening.", "LiveScribe")
                except Exception:
                    pass
                popup=tk.Toplevel(self.root)
                popup.title("LiveScribe")
                popup.attributes("-topmost",True)
                ttk.Label(popup,text="Transcription has started",padding=(20,14)).pack()
                popup.after(2800,popup.destroy)
            if kind=="line":
                self.rows.append(data)
                self.paint()
            if kind=="error":
                self.status.set(f"Transcription stopped · {data}")
                self.show()
            if kind=="finish":
                self.current=None
                if not self.status.get().startswith("Transcription stopped"):
                    self.status.set("Stopped · microphone off")
                self.start_button.configure(text="Start transcription",state="normal")
                self.tray.icon=icon()
                self.tray.title="LiveScribe · microphone off"
                self.tray.update_menu()
        run=self.current
        if run and run.ready and not run.stop.is_set() and run.skipped.is_set():
            self.status.set("Listening · some audio dropped. Try a smaller model or close heavy apps.")
        if self.quitting and not self.current and not self.importing:
            self.tray.stop()
            self.root.destroy()
            return
        self.root.after(60,self.poll)

    def exit(self):
        self.quitting=True
        if self.current:
            self.current.stop.set()
            self.status.set("Exiting · saving queued speech")

def main():
    if len(sys.argv) == 4 and sys.argv[1] == "--self-test":
        import wave
        import traceback
        result = Path(sys.argv[3])
        try:
            with wave.open(sys.argv[2], "rb") as f:
                if (f.getframerate(),f.getnchannels(),f.getsampwidth()) != (16000,1,2):
                    raise ValueError("Expected 16 kHz mono PCM16 test audio")
                pcm = np.frombuffer(f.readframes(f.getnframes()),dtype="<i2").astype(np.float32) / 32768
            text = open_engine(MODEL_BY_KEY["base"], RES / "models" / "base")(pcm,"en")
            result.write_text(text, encoding="utf-8")
            return 0 if "device" in text.lower() else 1
        except Exception:
            result.write_text(traceback.format_exc(),encoding="utf-8")
            return 1
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\LiveScribe-49d3")
    if ctypes.windll.kernel32.GetLastError() == 183:
        ctypes.windll.user32.MessageBoxW(None, "LiveScribe is already open. Check the system tray.", "LiveScribe", 0x40)
        return
    root=tk.Tk()
    App(root)
    root.mainloop()

if __name__=="__main__":
    raise SystemExit(main())
