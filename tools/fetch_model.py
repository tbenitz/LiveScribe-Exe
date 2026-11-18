"""Stage pinned model assets, optionally as a USB-transferable ZIP."""
import argparse
import hashlib
from pathlib import Path
import shutil
import sys
import tarfile
import urllib.request
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from desktop.core import MODEL_BY_KEY, model_ready

REVISIONS = {
    "tiny": "d90ca5fe260221311c53c58e660288d3deb8d356",
    "base": "ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66",
    "small": "536b0662742c02347bc0e980a01041f333bce120",
    "turbo": "0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf",
}
PARAKEET_ARCHIVE = "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2"
PARAKEET = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/" + PARAKEET_ARCHIVE

def download(url, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as response, temp.open("wb") as f:
        shutil.copyfileobj(response, f, 1024 * 1024)
    temp.replace(target)

def stage(key, root):
    model = MODEL_BY_KEY[key]
    folder = root/key
    folder.mkdir(parents=True, exist_ok=True)
    if key == "parakeet":
        source = PARAKEET
        if not model_ready(folder, model):
            archive = root/PARAKEET_ARCHIVE
            download(source, archive)
            with archive.open("rb") as file:
                if hashlib.file_digest(file, "sha256").hexdigest() != "1495e91b59d7fc53ddca91f3431758ec99f8fa253fdb0e1e851be0f72b14b0f9":
                    raise ValueError("Parakeet archive checksum did not match the upstream release")
            with tarfile.open(archive, "r:bz2") as tar:
                for item in tar:
                    name = Path(item.name).name
                    if item.isfile() and name in model.files:
                        with tar.extractfile(item) as i, (folder/name).open("wb") as o:
                            shutil.copyfileobj(i,o)
            archive.unlink()
        upstream = "https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3"
    else:
        upstream = "https://huggingface.co/openai/whisper-large-v3-turbo" if key == "turbo" else "https://github.com/openai/whisper"
        source = f"https://huggingface.co/{model.repo}/resolve/{REVISIONS[key]}"
        for f in (*model.files, *(("preprocessor_config.json",) if key == "turbo" else ())):
            if not (folder/f).is_file() or not (folder/f).stat().st_size:
                download(f"{source}/{f}",folder/f)
    if not model_ready(folder,model):
        raise ValueError("Incomplete model folder")
    (folder/"MODEL-SOURCE.txt").write_text(f"{model.name}\nUpstream: {upstream}\nDistribution: {source}\n", encoding="utf-8")
    return folder

def main():
    p=argparse.ArgumentParser()
    p.add_argument("model", choices=MODEL_BY_KEY)
    p.add_argument("--root", type=Path, default=Path("build/models"))
    p.add_argument("--zip-dir",type=Path)
    args=p.parse_args()
    folder=stage(args.model,args.root)
    if args.zip_dir:
        args.zip_dir.mkdir(parents=True,exist_ok=True)
        path=args.zip_dir/f"LiveScribe-model-{args.model}.zip"
        with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_STORED) as archive:
            for f in sorted(folder.iterdir()):
                if f.is_file() and not f.name.endswith(".part"):
                    archive.write(f,f"{folder.name}/{f.name}")
        with path.open("rb") as file:
            digest=hashlib.file_digest(file,"sha256").hexdigest()
        (path.parent/(path.name+".sha256")).write_text(f"{digest}  {path.name}\n",encoding="ascii")
    print(folder)

if __name__=="__main__":
    main()
