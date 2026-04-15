import os
import json
import argparse
import subprocess
import sys
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from queue import Queue
from config import DEVEVAL


def run_one_sample(key, workdir, args, mappers, saved_folder):
    completion_path = Path(mappers[key]["completion_path"])
    log_dir = saved_folder / completion_path.parent
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{key}.log"

    cmd = [
        sys.executable, str(Path(__file__).parent / "run_cg_one.py"),
        "--workdir", workdir,
        "--lv", str(args.lv),
        "--model_id", args.model_id,
        "--key", key,
        # "--max_steps", str(args.max_steps),
        "--outdir", args.outdir,
        "--mnr", str(args.mnr),
    ]
    # if args.no_stream:
    #     cmd.append("--no_stream")

    with open(log_file, "w") as lf:
        result = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT)
    return key, result.returncode, log_file


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lv", type=int, required=True, choices=[2, 3])
    parser.add_argument("--model_id", type=str, required=True)
    # parser.add_argument("--max_steps", type=int, default=20)
    # parser.add_argument("--no_stream", action="store_true")
    parser.add_argument("--outdir", type=str, default="results")
    parser.add_argument("--parallel", type=int, default=4, help="Number of parallel workers")
    parser.add_argument("--num_samples", type=int, default=None, help="Max samples to run (default: all)")
    parser.add_argument("--mnr", type=int, default=3)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    mapper_path = f"{DEVEVAL}/metadata/cg/lv{args.lv}/samples.json"

    with open(mapper_path, encoding="utf-8") as f:
        mappers = json.load(f)

    saved_folder = Path(f"{DEVEVAL}/{args.outdir}/oh/cg/lv{args.lv}/{args.model_id}")
    os.makedirs(saved_folder, exist_ok=True)

    status_file = saved_folder / "run_status.txt"

    run_samples_path = saved_folder / "run_samples.json"
    try:
        with open(run_samples_path) as f:
            run_samples = json.load(f)

        m = input(
            f"\033[33mYou've already run {len(run_samples)} samples. This run will proceed with the next {args.num_samples} samples ('c' - continue, 'r' - restart, '<other>' - quit)?\033[0m ")
        if m == "r":
            run_samples = {}
        elif m == "c":
            pass
        else:
            exit(0)
    except FileNotFoundError:
        run_samples = {}

    done_keys = set(run_samples.keys())
    keys = [k for k in mappers if k not in done_keys]
    if args.num_samples:
        keys = keys[:args.num_samples]

    NUM_PARALLEL = min(args.parallel, args.num_samples) if args.num_samples else args.parallel

    print(f"Running {len(keys)} samples with {NUM_PARALLEL} workers...")

    source = Path(f"{DEVEVAL}/Source_Code")


    def create_env(i):
        wd = Path(f"{DEVEVAL}/SC_oh_cg_lv{args.lv}_{args.model_id.replace('/', '_')}_env{i}")
        if wd.exists():
            print("Env already exists:", wd)
        else:
            shutil.copytree(source, wd, symlinks=True, ignore_dangling_symlinks=True)
            print("Created env:", wd)
        return wd


    with ThreadPoolExecutor(max_workers=NUM_PARALLEL) as ex:
        workdirs = list(ex.map(create_env, range(NUM_PARALLEL)))

    free_envs = Queue()
    for i in range(len(workdirs)):
        free_envs.put(i)


    def run_one_dynamic(key):
        worker_idx = free_envs.get()
        try:
            return run_one_sample(key, workdirs[worker_idx].name, args, mappers, saved_folder)
        finally:
            free_envs.put(worker_idx)


    with ThreadPoolExecutor(max_workers=NUM_PARALLEL) as executor:
        futures = {executor.submit(run_one_dynamic, key): key for key in keys}
        for future in as_completed(futures):
            key, returncode, log_file = future.result()

            if returncode == 0:
                msg = f"[OK] {key}"
            else:
                msg = f"[FAIL] {key}, see: {log_file}"
            print(msg)
            with open(status_file, "a") as sf:
                sf.write(msg + "\n")
            # status = "OK" if returncode == 0 else "FAIL"
            # print(f"[{status}] {key}")
