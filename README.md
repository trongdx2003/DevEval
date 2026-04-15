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

# Installation
## smolagents
```bash
uv pip install "smolagents[toolkit]"
uv pip install "smolagents[openai]"
```

For more information, visit: [https://huggingface.co/docs/smolagents/installation](https://huggingface.co/docs/smolagents/installation)

## OpenHands
**Note:** This library requires `python >= 3.12`
```bash
uv pip install openhands-sdk # Core SDK (openhands.sdk)
uv pip install openhands-tools  # Built-in tools (openhands.tools)
# Optional: required for sandboxed workspaces in Docker or remote servers
uv pip install openhands-workspace # Workspace backends (openhands.workspace)
uv pip install openhands-agent-server # Remote agent server (openhands.agent_server)
```
# Configuration

## smolagents

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

## OpenHands

Open the file `agents/oh/config.py`.

* Modify the `DEVEVAL` variable.
* Modify the line `llm = LLM(
        model=f"openrouter/{model}", 
        api_key=API_KEY, 
        base_url="https://openrouter.ai/api/v1")` to suit your case. Please refer to https://docs.openhands.dev/sdk/arch/llm


Afterward, change the model name in the line:

```
model = "openai/gpt-4o-mini"
```

Then run:

```bash
python config.py
```


to verify the configuration.

# Running

For `smolagents`:

```bash
python agents/sm/run_*_batch.py [--options]
```

For `OpenHands`:
```bash
python agents/oh/run_*_batch.py [--options]
```

where `*` can be:

* `cg` (code generation)
* `exec` (execution and testing)
* `fm` (file management)

### Available options

* `--model_id` (required): the name of the LLM used in the `openrouter_model` function above.

* `--lv` (required):
  * For code generation: `--lv [1 | 2 | 3]` (Note: For `openhands`, use only 2 or 3)
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

You may encounter `FileNotFoundError` in some samples (but not all) (view `.log` file), like: 
```bash
FileNotFoundError: [Errno 2] No such file or directory: '/home/xuanlong/Misbehaviors/misbehavior/DevEval/SC_oh_cg_lv2_google_gemini-2.5-flash_env0/Text-Processing/dominate/dominate/dom_tag_missing__get_thread_context.py'
```
It's ok, let the script continue running until completion. After the run finishes, remove the generated directory for the failed task:
```bash
rm -r SC_oh_cg_lv2_google_gemini-2.5-flash_env0
```
Alternatively, you can remove all related directories for the model and the task (in this case, `cg_lv2`):
```bash
rm -r SC_oh_cg_lv2_google_gemini-2.5-flash_env*
```
Then rerun the script `run_*_batch.py`, it will report the number of successfully ran samples.
If you accidentally request more samples than needed, press `'q' + Enter` to quit. (For example, you already processed 190 samples and you only need 10 more but specifying `--num_samples 20`)
Then rerun `run_*_batch.py --num_samples <remaining>`.
