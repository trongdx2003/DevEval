import json
import shutil
from pathlib import Path

with open("metadata/fm/delif/samples.json") as f:
    dat = json.load(f)

for k, v in dat.items():
    src = v["taken_from"]
    dst = v["completion_path"]

    for file in src:
        shutil.copy2(Path("Source_Code") / file, Path("Source_Code_fmdelif") / dst)

print("Done")