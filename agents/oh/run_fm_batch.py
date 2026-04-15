import json
import argparse
import subprocess
import sys
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
from config import DEVEVAL


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lv", type=str, required=True)
    parser.add_argument("--model_id", type=str, required=True)
    parser.add_argument("--num_samples", type=int, default=50)
    parser.add_argument("--outdir", type=str, default="results")
    parser.add_argument("--mnr", type=int, default=3)
    parser.add_argument("--parallel", type=int, default=4, help="Number of parallel workers")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    run_samples_path = Path(f"{DEVEVAL}/{args.outdir}/oh/fm/{args.lv}/{args.model_id}/run_samples.json")

    with open(f"{DEVEVAL}/metadata/fm/{args.lv}/samples.json", encoding="utf-8") as f:
        mappers = json.load(f)

    try:
        with open(run_samples_path) as f:
            already_done = set(json.load(f).keys())

        m = input(f"\033[33mYou've already run {len(already_done)} samples. This run will proceed with the next {args.num_samples} samples? ('c' - continue (ok), 'r' - restart, '<other>' - quit)\033[0m ")
        if m == "c":
            pass
        elif m == "r":
            already_done = set()
            run_samples_path.write_text("{}")
        else:
            sys.exit(0)

    except FileNotFoundError:
        already_done = set()

    pending = [k for k in mappers if k not in already_done]
    print(f"Pending: {len(pending)} samples, running up to {args.num_samples}")

    source = Path(f"{DEVEVAL}/Source_Code") if args.lv != "delif" else Path(f"{DEVEVAL}/Source_Code_fmdelif")
    n_envs = min(args.parallel, args.num_samples)

    def create_env(i):
        wd = Path(f"{DEVEVAL}/SC_oh_fm_{args.lv}_{args.model_id.replace('/', '_')}_env{i}")
        if wd.exists():
            print("Env already exists:", wd)
        else:
            shutil.copytree(source, wd, symlinks=True, ignore_dangling_symlinks=True)
            print("Created env:", wd)
        return wd

    with ThreadPoolExecutor(max_workers=n_envs) as ex:
        workdirs = list(ex.map(create_env, range(n_envs)))

    base_cmd = [
        sys.executable, str(Path(__file__).parent / "run_fm_one.py"),
        "--lv", args.lv,
        "--model_id", args.model_id,
        #"--max_steps", str(args.max_steps),
        "--outdir", args.outdir,
        "--mnr", str(args.mnr),
    ]
    # if args.no_stream:
    #     base_cmd.append("--no_stream")

    saved_base = Path(f"{DEVEVAL}/{args.outdir}/oh/fm/{args.lv}/{args.model_id}")
    status_file = saved_base / "run_status.txt"
    saved_base.mkdir(parents=True, exist_ok=True)

    free_envs = Queue()
    for i in range(len(workdirs)):
        free_envs.put(i)

    batch = pending[:args.num_samples]
    print(f"Running {len(batch)} samples with {min(args.parallel, args.num_samples)} workers...")

    def run_one(k):
        worker_idx = free_envs.get()
        try:
            completion_path = Path(mappers[k]["completion_path"])
            log_dir = saved_base / completion_path.parent if args.lv != "delif" else saved_base / completion_path
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"{k}.log"
            with open(log_file, "w") as lf:
                result = subprocess.run(
                    base_cmd + ["--workdir", workdirs[worker_idx].name, "--key", k],
                    stdout=lf, stderr=subprocess.STDOUT
                )
            msg = f"[done] {k}" if result.returncode == 0 else f"[warn] non-zero exit for {k}, see {log_file}"
            print(msg)
            with open(status_file, "a") as sf:
                sf.write(msg + "\n")
        finally:
            free_envs.put(worker_idx)

    with ThreadPoolExecutor(max_workers=min(args.parallel, args.num_samples)) as executor:
        futures = {executor.submit(run_one, k): k for k in batch}
        for f in as_completed(futures):
            f.result()

    print(f"\nDone. Ran {len(batch)} samples.")
