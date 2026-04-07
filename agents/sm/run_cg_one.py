import os
import json
import argparse
import time
import shutil
import re
import fcntl

from pathlib import Path
from contextlib import redirect_stdout

from smolagents import CodeAgent

from utils import find_recent_modified_files
from config import openrouter_model, run_and_record, all_builtins, DEVEVAL


def extract_python_code(text: str) -> str:
    pattern = r"```python\s*(.*?)```"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()


def is_updated(filepath, minutes=5):
    try:
        return (time.time() - os.path.getmtime(filepath)) <= minutes * 60
    except FileNotFoundError:
        return False


def run_one(lv, model_id, sample_key, max_steps, agent_tools, additional_imports,
            stream_outputs, saved_folder, executor_kwargs):
    os.makedirs(saved_folder, exist_ok=True)
    saved_folder = Path(saved_folder)

    with open(f"{DEVEVAL}/all_files_cg.txt") as f:
        all_expected_files = {line.strip() for line in f}

    model = openrouter_model(model_id)
    agent = CodeAgent(
        model=model,
        tools=agent_tools,
        additional_authorized_imports=additional_imports,
        max_steps=max_steps,
        stream_outputs=stream_outputs,
        executor_kwargs=executor_kwargs,
    )

    infor = mappers[sample_key]
    prompt = infor["prompt"]
    completion_path = infor["completion_path"]
    new_completion_path = Path(infor["new_completion_path"])

    # COPY THE FILE WITH MISSING FUNCTION FROM THE DATA FOLDER
    shutil.copy2(
        Path("Source_Code_no_code") / new_completion_path,
        Path(RUN_ENV) / Path(completion_path).parent
    )

    os.chdir(RUN_ENV)

    # TEMPORARILY DELETE THE GROUND TRUTH
    Path(completion_path).unlink(missing_ok=True)

    # Create saved folder and run history file
    os.makedirs(saved_folder / new_completion_path.parent, exist_ok=True)
    history_file = saved_folder / new_completion_path.parent / f"run_history_{sample_key}.txt"

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

    if lv == "lv1":
        code = extract_python_code(response)
        if not is_updated(new_completion_path):
            with open(new_completion_path, 'w') as f:
                f.write(code)
        else:
            with open(saved_folder / "updated_completion.txt", 'a', encoding="utf-8") as f:
                f.write(str(new_completion_path) + "\n")

    # MOVE THE COMPLETED FILE TO THE SAVED FOLDER
    src = Path(RUN_ENV) / new_completion_path
    dst = saved_folder / new_completion_path
    if dst.exists():
        dst.unlink()
    os.makedirs(dst.parent, exist_ok=True)
    shutil.move(src, dst.parent)

    os.chdir(DEVEVAL)

    # =================================
    # Find recently modified files
    elapsed_minutes = (time.time() - start_time) / 60 + 0.5
    recent_modified_files = find_recent_modified_files(RUN_ENV, minutes=elapsed_minutes)

    created_files, updated_files = [], []

    for file in recent_modified_files:
        if file.endswith(".pyc"):  # IGNORE ALL .pyc FILES
            continue
        if not os.path.exists(f"{DEVEVAL}/Source_Code/{file}"):
            # If the file does not exist in the ground-truth, it is a new created file
            created_files.append(file)
        else:
            # If the file does exist in the ground-truth, it is updated
            updated_files.append(file)

    # Ignore the ground-truth file since we temporarily removed it
    deleted_files = {f for f in all_expected_files if f != completion_path and not os.path.lexists(f"{RUN_ENV}/{f}")}

    with open(saved_folder / "file_history.txt", 'a', encoding="utf-8") as f:
        with redirect_stdout(f):
            print(f"## Sample: {sample_key}")
            print("Recent modified files:", recent_modified_files)
            print("Created files", created_files)
            print("Updated files", updated_files)
            print("Deleted files", list(deleted_files))
            print()

    # Back-up the running environment
    for file in deleted_files:
        shutil.copy2(f"Source_Code/{file}", f"{RUN_ENV}/{file}")
    for file in updated_files:
        shutil.copy2(f"Source_Code/{file}", f"{RUN_ENV}/{file}")
    for file in created_files:
        os.unlink(f"{RUN_ENV}/{file}")

    # Restore the ground-truth file
    shutil.copy2(f"Source_Code/{completion_path}", Path(RUN_ENV) / Path(completion_path).parent)

    run_samples_path = saved_folder / "run_samples.json"
    lock_path = run_samples_path.with_suffix(".lock")

    with open(lock_path, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            with open(run_samples_path) as f:
                run_samples = json.load(f)
        except FileNotFoundError:
            run_samples = {}

        run_samples[sample_key] = {
            "completion_path": infor["completion_path"],
            "new_completion_path": infor["new_completion_path"],
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

    print(f"Done: {sample_key}")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir", type=str, required=True)
    parser.add_argument("--lv", type=int, required=True, choices=[1, 2, 3])
    parser.add_argument("--model_id", type=str, required=True)
    parser.add_argument("--key", type=str, required=True, help="Sample key to run")
    parser.add_argument("--max_steps", type=int, default=20)
    parser.add_argument("--no_stream", action="store_true")
    parser.add_argument("--outdir", type=str, default="results")
    parser.add_argument("--mnr", type=int, default=3)
    return parser.parse_args()


if __name__ == "__main__":
    from tools import *

    args = parse_args()

    mapper_path = f"{DEVEVAL}/metadata/cg/lv{args.lv}/samples.json"

    with open(mapper_path, encoding="utf-8") as f:
        mappers = json.load(f)

    SAVED_FOLDER = f"{DEVEVAL}/{args.outdir}/cg/lv{args.lv}/{args.model_id}"
    RUN_ENV = f"{DEVEVAL}/{args.workdir}"

    AVAILABLE_TOOLS = [read_file, update_content, remove_file]

    run_one(
        lv=f"lv{args.lv}",
        model_id=args.model_id,
        sample_key=args.key,
        max_steps=args.max_steps,
        stream_outputs=not args.no_stream,
        agent_tools=AVAILABLE_TOOLS,
        additional_imports=["*"],
        saved_folder=SAVED_FOLDER,
        executor_kwargs={"additional_functions": all_builtins},
    )
