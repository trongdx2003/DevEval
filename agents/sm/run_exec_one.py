import os
import json
import argparse
import time
import shutil
import fcntl

from pathlib import Path
from contextlib import redirect_stdout

from smolagents import CodeAgent

from utils import find_recent_modified_files
from tools import read_file, update_content, remove_file
from config import openrouter_model, run_and_record, all_builtins, DEVEVAL


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--key", type=str, required=True, help="Mapper key (sample id)")
    parser.add_argument("--workdir", type=str, required=True)
    parser.add_argument("--lv", type=str, required=True)
    parser.add_argument("--model_id", type=str, required=True)
    parser.add_argument("--max_steps", type=int, default=20)
    parser.add_argument("--no_stream", action="store_true")
    parser.add_argument("--outdir", type=str, default="results")
    parser.add_argument("--mnr", type=int, default=3)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    RUN_ENV = f"{DEVEVAL}/{args.workdir}"
    SAVED_FOLDER = Path(f"{DEVEVAL}/{args.outdir}/exec/{args.lv}/{args.model_id}")
    os.makedirs(SAVED_FOLDER, exist_ok=True)

    with open(f"{DEVEVAL}/metadata/exec/{args.lv}/samples.json", encoding="utf-8") as f:
        mappers = json.load(f)

    with open(f"{DEVEVAL}/all_files_cg.txt") as f:
        all_expected_files = {line.strip() for line in f}

    run_samples_path = SAVED_FOLDER / "run_samples.json"
    lock_path = run_samples_path.with_suffix(".lock")

    with open(lock_path, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            with open(run_samples_path) as f:
                run_samples = json.load(f)
        except FileNotFoundError:
            run_samples = {}
        fcntl.flock(lock, fcntl.LOCK_UN)

    k = args.key
    if k in run_samples:
        print(f"[skip] {k} already done")
        raise SystemExit(0)

    infor = mappers[k]
    prompt = infor["prompt"]
    completion_path = Path(infor["completion_path"])
    _name = infor["function_name"].replace(".", "_")

    model = openrouter_model(args.model_id)
    agent = CodeAgent(
        model=model,
        tools=[read_file, update_content, remove_file],
        additional_authorized_imports=["*"],
        max_steps=args.max_steps,
        stream_outputs=not args.no_stream,
        executor_kwargs={"additional_functions": all_builtins},
    )

    os.chdir(RUN_ENV)
    os.makedirs(SAVED_FOLDER / completion_path.parent, exist_ok=True)
    history_file = SAVED_FOLDER / completion_path.parent / f"run_history_{k}.txt"

    start_time = time.time()
    no_response_count = 0
    try:
        response = run_and_record(agent, prompt, write_history_to=history_file)
        while not response and no_response_count < args.mnr:
            response = run_and_record(agent, prompt, write_history_to=history_file)
            no_response_count += 1
            time.sleep(2)
    except Exception:
        response = None

    shutil.copy2(
        Path(RUN_ENV) / completion_path,
        SAVED_FOLDER / completion_path.parent / f"{k}_{completion_path.stem}_{args.lv}_{_name}.py",
        follow_symlinks=False
    )

    os.chdir(DEVEVAL)

    created_files, updated_files = [], []
    elapsed_minutes = (time.time() - start_time) / 60 + 0.5
    recent_modified_files = find_recent_modified_files(RUN_ENV, minutes=elapsed_minutes)

    for file in recent_modified_files:
        if file.endswith(".pyc"):
            continue
        if not os.path.exists(f"{DEVEVAL}/Source_Code/{file}"):
            created_files.append(file)
        else:
            updated_files.append(file)

    deleted_files = {f for f in all_expected_files if not os.path.lexists(f"{RUN_ENV}/{f}")}

    with open(SAVED_FOLDER / "file_history.txt", 'a', encoding="utf-8") as f:
        with redirect_stdout(f):
            print(f"## Sample: {k}")
            print("Recent modified files:", recent_modified_files)
            print("Created files", created_files)
            print("Updated files", updated_files)
            print("Deleted files", list(deleted_files))
            print()

    for file in deleted_files:
        src, dst = Path(f"Source_Code/{file}"), Path(f"{RUN_ENV}/{file}")
        if src.resolve() != dst.resolve():
            shutil.copy2(src, dst, follow_symlinks=False)

    for file in updated_files:
        src, dst = Path(f"Source_Code/{file}"), Path(f"{RUN_ENV}/{file}")
        if src.resolve() != dst.resolve():
            shutil.copy2(src, dst, follow_symlinks=False)

    for file in created_files:
        os.unlink(f"{RUN_ENV}/{file}")

    src = Path("Source_Code") / completion_path
    dst = Path(RUN_ENV) / completion_path.parent
    if src.resolve() != (dst / completion_path.name).resolve():
        shutil.copy2(src, dst, follow_symlinks=False)

    # Atomic update of run_samples.json (locked for parallel safety)
    with open(lock_path, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            with open(run_samples_path) as f:
                run_samples = json.load(f)
        except FileNotFoundError:
            run_samples = {}

        run_samples[k] = {
            "completion_path": infor["completion_path"],
            "new_completion_path": f"{k}_{completion_path.stem}_{args.lv}_{_name}.py",
            "function_name": infor["function_name"],
            "need_read": infor["need_read"],
            "file_create": len(created_files),
            "file_delete": len(deleted_files),
            "file_update": len(updated_files),
            "no_response": not bool(response),
        }

        with open(run_samples_path, "w") as f:
            json.dump(run_samples, f, indent=4)
        fcntl.flock(lock, fcntl.LOCK_UN)

    print(f"[done] {k}")
