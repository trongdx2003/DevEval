import json
import argparse
import subprocess
import sys
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import DEVEVAL


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lv", type=str, required=True)
    parser.add_argument("--model_id", type=str, required=True)
    parser.add_argument("--num_samples", type=int, default=200)
    parser.add_argument("--outdir", type=str, default="results")
    parser.add_argument("--mnr", type=int, default=3)
    parser.add_argument("--parallel", type=int, default=4, help="Number of parallel workers")
    return parser.parse_args()


if __name__ == "__main__":
    import sys

    args = parse_args()

    run_samples_path = Path(f"{DEVEVAL}/{args.outdir}/oh/exec/{args.lv}/{args.model_id}/run_samples.json")

    with open(f"{DEVEVAL}/metadata/exec/{args.lv}/samples.json", encoding="utf-8") as f:
        mappers = json.load(f)

    try:
        with open(run_samples_path) as f:
            already_done = set(json.load(f).keys())

            m = input(
                f"\033[33mYou've already run {len(already_done)} samples. This run will proceed with the next {args.num_samples} samples? ('c' - continue (ok), 'r' - restart, '<other>' - quit)\033[0m ")

            if m == "c":
                pass
            elif m == "r":
                already_done = set()
            else:
                sys.exit(0)

    except FileNotFoundError:
        already_done = set()

    pending = [k for k in mappers if k not in already_done]
    print(f"Pending: {len(pending)} samples, running up to {args.num_samples}")

    source = Path(f"{DEVEVAL}/Source_Code")

    NUM_PARALLEL = min(args.parallel, args.num_samples)


    def create_env(i):
        wd = Path(f"{DEVEVAL}/SC_oh_exec_{args.lv}_{args.model_id.replace('/', '_')}_env{i}")
        if wd.exists():
            print("Env already exists:", wd)
        else:
            shutil.copytree(source, wd, symlinks=True, ignore_dangling_symlinks=True)
            print("Created env:", wd)
        return wd


    with ThreadPoolExecutor(max_workers=NUM_PARALLEL) as ex:
        workdirs = list(ex.map(create_env, range(NUM_PARALLEL)))

    base_cmd = [
        sys.executable, str(Path(__file__).parent / "run_exec_one.py"),
        "--lv", args.lv,
        "--model_id", args.model_id,
        "--outdir", args.outdir,
        "--mnr", str(args.mnr),
    ]

    saved_base = Path(f"{DEVEVAL}/{args.outdir}/oh/exec/{args.lv}/{args.model_id}")

    status_file = saved_base / "run_status.txt"


    def run_one(args_tuple):
        k, worker_idx = args_tuple
        completion_path = Path(mappers[k]["completion_path"])
        log_dir = saved_base / completion_path.parent
        log_dir.mkdir(parents=True, exist_ok=True)
        # log_file = log_dir / f"{k.replace('/', '_')}_{args.lv}_{args.model_id.replace('/', '_')}.log"
        log_file = log_dir / f"{k}.log"

        with open(log_file, "w") as lf:
            result = subprocess.run(
                base_cmd + ["--workdir", workdirs[worker_idx].name, "--key", k],
                stdout=lf, stderr=subprocess.STDOUT
            )

        if result.returncode != 0:
            msg = f"[warn] non-zero exit for {k}, see {log_file}"
        else:
            msg = f"[done] {k}"

        print(msg)
        with open(status_file, "a") as sf:
            sf.write(msg + "\n")


    batch = pending[:args.num_samples]
    print(f"Running {len(batch)} samples with {NUM_PARALLEL} workers...")

    from queue import Queue

    free_envs = Queue()
    for i in range(len(workdirs)):
        free_envs.put(i)


    def run_one_dynamic(k):
        worker_idx = free_envs.get()
        try:
            run_one((k, worker_idx))
        finally:
            free_envs.put(worker_idx)


    with ThreadPoolExecutor(max_workers=NUM_PARALLEL) as executor:
        futures = {executor.submit(run_one_dynamic, k): k for k in batch}
        for f in as_completed(futures):
            f.result()

    print(f"\nDone. Ran {len(batch)} samples.")
