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


# Abbreviations
tasks = {
    "delf": "delete_file",
    "delif": "delete_irrelevant_files",
    "anf": "add_new_files",
    "aef": "add_existing_files"
}


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
    lv = args.lv

    RUN_ENV = f"{DEVEVAL}/{args.workdir}"
    SAVED_FOLDER = Path(f"{DEVEVAL}/{args.outdir}/fm/{lv}/{args.model_id}")
    os.makedirs(SAVED_FOLDER, exist_ok=True)

    with open(f"{DEVEVAL}/metadata/fm/{args.lv}/samples.json", encoding="utf-8") as f:
        mappers = json.load(f)

    # ===================
    # For the task of deleting irrelevant files (delif), the running environments include some dummy files

    ground_truth = "Source_Code_fmdelif" if lv == "delif" else "Source_Code"

    if lv == "delif":
        with open(f"{DEVEVAL}/all_files_fm_delif.txt") as f:
            all_expected_files = {line.strip() for line in f}
    else:
        with open(f"{DEVEVAL}/all_files_fm.txt") as f:
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
    history_file = SAVED_FOLDER / completion_path.parent / f'run_history_{k}.txt'

    if lv == "aef" or lv == "anf":
        modify_all_expected_files = False
        modify_unexpected_file = False
        need_update_files = infor["need_update"]
        count_modify_all_expected_files = 0

    elif lv == "delf" or lv == "delif":
        delete_unexpected_file = False
        delete_expected_file = False

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

    elapsed_minutes = (time.time() - start_time) / 60 + 0.5
    recent_modified_files = find_recent_modified_files(RUN_ENV, minutes=elapsed_minutes)

    created_files, updated_files = [], []
    for file in recent_modified_files:
        if file.endswith(".pyc"):
            continue
        if not os.path.exists(f"{DEVEVAL}/{ground_truth}/{file}"):
            created_files.append(file)
        else:
            updated_files.append(file)
            if lv == "aef" or lv == "anf":
                # =======================================
                # For the task of adding a function to a new file or adding it to a specific file
                if file not in need_update_files:
                    modify_unexpected_file = True
                else:
                    count_modify_all_expected_files += 1
                    if count_modify_all_expected_files == len(need_update_files):
                        modify_all_expected_files = True

    if lv == "aef":
        # ====================
        # For add existing files, the agent must update the following files:
        # (i) The current file;
        # (ii) The file we asked the agent to add that function to,
        # (iii) The files referenced to that function
        # We copied these files to see their changes (if any)

        for file in need_update_files:
            current_completion_path = Path(file)
            if file != infor["completion_path"]:
                if file != need_update_files[-1]:
                    shutil.copy2(
                        file,
                        SAVED_FOLDER / completion_path.parent / f"references_{k}_{current_completion_path.stem}.py",
                        follow_symlinks=False
                    )
                else:
                    shutil.copy2(
                        file,
                        SAVED_FOLDER / completion_path.parent / f"updated_{k}_{current_completion_path.stem}.py",
                        follow_symlinks=False
                    )
            else:
                shutil.copy2(
                    file,
                    SAVED_FOLDER / completion_path.parent / f"updated_{k}_{completion_path.stem}.py",
                    follow_symlinks=False
                )

    elif lv == "anf":
        # ====================
        # For add new files, the agent must update the following files:
        # (i) The current file;
        # and (ii) The files referenced to that function
        # We copied these files to see their changes (if any)

        created_file_dir = SAVED_FOLDER / completion_path.parent / f"created_files_{k}_{lv}"
        os.makedirs(created_file_dir, exist_ok=True)

        for file in created_files:
            shutil.copy2(file, created_file_dir, follow_symlinks=False)

        for file in need_update_files:
            current_completion_path = Path(file)
            if file != infor["completion_path"]:
                shutil.copy2(
                    file,
                    SAVED_FOLDER / completion_path.parent / f"references_{k}_{current_completion_path.stem}.py",
                    follow_symlinks=False
                )
            else:
                shutil.copy2(
                    file,
                    SAVED_FOLDER / completion_path.parent / f"updated_{k}_{completion_path.stem}.py",
                    follow_symlinks=False
                )

    os.chdir(DEVEVAL)

    deleted_files = {f for f in all_expected_files if not os.path.lexists(f"{RUN_ENV}/{f}")}

    for file in deleted_files:
        shutil.copy2(f"{ground_truth}/{file}", f"{RUN_ENV}/{file}", follow_symlinks=False)

        if lv == "delf":
            if file != infor["completion_path"]:
                delete_unexpected_file = True
            else:
                delete_expected_file = True

        elif lv == "delif":
            dummies = infor["dm"]
            if file not in dummies:
                delete_unexpected_file = True
            else:
                delete_expected_file = True

    with open(SAVED_FOLDER / "file_history.txt", 'a', encoding="utf-8") as f:
        with redirect_stdout(f):
            print(f"## Sample: {k}")
            print("Recent modified files:", recent_modified_files)
            print("Created files", created_files)
            print("Updated files", updated_files)
            print("Deleted files", list(deleted_files))
            if lv in ("delf", "delif"):
                print("Delete unexpected files", delete_unexpected_file)
                print("Delete expected files", delete_expected_file)
            # if lv == "delif":
            #     print("Delete expected files", delete_expected_file)
            elif lv == "aef" or lv == "anf":
                print("Modify all expected files", modify_all_expected_files)
                print("Modify unexpected_file", modify_unexpected_file)
            print()

    for file in updated_files:
        shutil.copy2(f"{ground_truth}/{file}", f"{RUN_ENV}/{file}", follow_symlinks=False)

    for file in created_files:
        os.unlink(f"{RUN_ENV}/{file}")

    # Atomic update of run_samples.json (locked for parallel safety)
    with open(lock_path, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            with open(run_samples_path) as f:
                run_samples = json.load(f)
        except FileNotFoundError:
            run_samples = {}

        if lv == "delf" or lv == "delif":
            run_samples[k] = {
                "completion_path": infor["completion_path"],
                "file_create": len(created_files),
                "file_delete": len(deleted_files),
                "file_update": len(updated_files),
                "delete_unexpected_file": delete_unexpected_file,
                "delete_expected_file": delete_expected_file,
            }

        elif lv == "anf" or lv == "aef":
            run_samples[k] = {
                "completion_path": infor["completion_path"],
                "new_completion_path": str(completion_path.parent / f"updated_{k}_{completion_path.stem}.py").replace(
                    "\\", "/"),
                "need_update": infor["need_update"],
                "function_name": infor["function_name"],
                "file_create": len(created_files),
                "file_delete": len(deleted_files),
                "file_update": len(updated_files),
                "modify_all_expected_files": modify_all_expected_files,
                "modify_unexpected_file": modify_unexpected_file,
            }

        with open(run_samples_path, "w") as f:
            json.dump(run_samples, f, indent=4)
        fcntl.flock(lock, fcntl.LOCK_UN)

    print(f"[done] {k}")
