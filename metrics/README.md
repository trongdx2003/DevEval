
* `run_fileread.py`: Evaluates the FILE READ metric (i.e., whether the model reads all required dependencies).
* `run_rb.py`: Evaluates all metrics for completed samples, including: **Syntax, Context, Signature, Body Change, File Read, File Update, File Delete**

Please give a check for `metrics/rb/parsefile.py` and `metrics/rb/metrics.py`. You may try parsing a file using the function `parse` defined in `metrics/rb/parsefile.py`.

# Running

```bash 
python metrics/run_*.py [--options]
```

Common arguments:
* `--outdir`: Output directory (e.g., `results/sm`, `results/oh`). You can change "results" depending on where your outputs are stored (if the output of `smolagents` does not put in subfolder `sm`, then `--outdir results`)
* `--task`: `cg/lv[1|2|3]`, `exec/[execute|testing]`, `fm/[delf|delif|anf|aef]`
* `--model_id`: model name
* `--new` (optional): Use this flag if you modified `run_fileread.py` or `run_rb.py`. Safe to always include for fresh evaluation

Another arguments for `run_fileread.py`:
* `--rb` | `--llm` (required: choose one): Measure FILE READ using LLM-based evaluation or Rule-based evaluation
    * For `smolagents`, use `--llm` (more accurate; rule-based not fully reliable yet)
    * For `openhands`, use `--rb` (fast and accurate; no LLM judge implemented)

* `--workers` (optional, default to 4): Number of parallel workers
* For `--llm`, you may specify the following arguments:
  * `--num_samples` (default to 5): Number of evaluation samples
  * `--jm` (default to "google/gemini-3-flash-preview"): judge model
  * `--temp` (default `0.1`): Temperature for the judge model