# Data setup

Download the DevEval dataset from [here](https://huggingface.co/datasets/LJ0815/DevEval/blob/main/Source_Code.tar.gz) and move the zip to the **DevEval** folder.

Run the commands below:
```bash
cd DevEval 

tar -xzf Source_Code.tar.gz

find Source_Code -type d -name "__pycache__" -exec rm -r {} +

cp -a Source_Code Source_Code_fmdelif

python create_delif.py
```

**Note**: `all_*` txt files and the folder `Source_Code_no_code` are necessary.

Here’s a refined version with clearer, more precise English and improved grammar while keeping it concise:


# Installation
```bash
uv pip install "smolagents[toolkit]"
uv pip install "smolagents[openai]"
```

For more information, visit: [https://huggingface.co/docs/smolagents/installation](https://huggingface.co/docs/smolagents/installation)

# Configuration

Open the file `agents/sm/config.py`.

* Modify the `DEVEVAL` variable.
* Customize the `openrouter_model` function.
  (Currently, it uses `OpenAIModel` to run closed-source models. If this does not suit your use case, refer to the [installation page](https://huggingface.co/docs/smolagents/installation) and the [Models API reference](https://huggingface.co/docs/smolagents/reference/models).)

Afterward, set the model name in the line:

```
model = openrouter_model("...")
```

Then run:

```bash
python config.py
```

to verify the configuration.

# Running

```bash
python agents/sm/run_*_batch.py [--options]
```

where `*` can be:

* `cg` (code generation)
* `exec` (execution and testing)
* `fm` (file management)

### Available options

* `--model_id` (required): the name of the LLM used in the `openrouter_model` function above.

* `--lv` (required):
  * For code generation: `--lv [1 | 2 | 3]`
  * For execution and testing: `--lv [execute | testing]`
  * For file management: `--lv [delf | delif | aef | anf]`
    * `delf`: delete file
    * `delif`: delete irrelevant file
    * `aef`: add existing file
    * `anf`: add new file

* `--outdir` (optional, default: `results`): directory to store agent outputs and log files (created automatically if it does not exist).

* `--num_samples` (optional):

  * Default: `200` for code generation, execution, and testing; `50` for other tasks.
  * It is recommended to set a small value (e.g., `--num_samples 2`) for initial testing.

* `--parallel` (optional, default: `4`): number of parallel workers.


Completed samples are tracked across runs. If at least one sample has successfully done, you will be prompted to continue with the next set of samples in subsequent runs.

Example:

```bash
python agents/sm/run_cg_batch.py --model_id "openai/gpt-4o-mini" --lv 1 --num_samples 2 [--outdir myoutdir]

[done] s1
[done] s2

python agents/sm/run_cg_batch.py --model_id "openai/gpt-4o-mini" --lv 1 --num_samples 2 [--outdir myoutdir]
You've already run 2 samples. This run will proceed with the next 2 samples ('c' - continue, 'r' - restart, '<other>' - quit)
```

After successfully running 2 samples, you can continue with the remaining samples (e.g., the next 198).

### Errors you may meet

If you encounter `FileNotFoundError` in some samples (but not all) (view log file), it's ok. Simply count the number of failed runs (in the file `run_status.txt`) and rerun the script with that number of samples.