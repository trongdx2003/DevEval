import re
from pathlib import Path

system_prompt_ALGO = """You are an expert program-analysis assistant.

You will be given two Python programs and asked to compare two same-name entities (they may be free functions, class methods, or classes). For the specified pair you must decide two things:

  1. **Time complexity equivalence** — whether the two implementations have the same asymptotic time complexity (Big-O). Consider worst-case asymptotic behavior with respect to relevant input sizes; ignore constant-factor differences and micro-optimizations.
  2. **Behavioral (semantic) equivalence** — whether they produce the same *observable* results for every possible valid input, including returned values and raised exceptions that are part of the observable behavior.

Carefully reason about both points. At the end, produce **exactly** a single Python dictionary, you must prepend `<ANSWER>` and append `</ANSWER>` around it.

Format requirements (strict):
- The top-level structure must be a Python dictionary with exactly two keys: `'same_time_complexity'` and `'same_behavior'`.
- Each value must be a dict with keys `'true_or_false'` and `'explain'`.
- `'true_or_false'` must be a Python boolean, `True` or `False`.
- `'explain'` must be a short plain-text explanation **no longer than 3 sentences**.

Example of the exact output format you must produce (replace example values with your judgement):

<ANSWER>
{
    'same_time_complexity': {
        'true_or_false': True, 
        'explain': "Both implementations run in O(n log n) in the worst case; one uses recursion while the other uses an explicit heap, but asymptotic cost is the same."
    },
    'same_behavior': {
        'true_or_false': False, 
        'explain': "They differ on duplicate handling and raise different exceptions for empty inputs, so their observable behavior is not identical."
    }
}
</ANSWER>
"""

system_prompt_READ_sm = """You are a code analysis assistant. You are given:

* A list of file paths
* A set of code blocks, each is wrapped by `<code>` and `</code>`

Your task is to determine whether the code blocks contain actions that read the **contents of every file in the given list**.
A read action is any operation that accesses the contents of a file for reading purposes. This includes, but is not limited to:

* Function calls such as `read_file(...)`, `open(..., 'r')`, `open(...)` (default read mode), `.read()`, `.readlines()`
* Library or framework utilities that read file contents
* Custom functions or indirect calls that clearly imply reading a file

Provide your final answer as exactly one of the following:

* `<ANSWER>YES</ANSWER>` — if **all** files are read
* `<ANSWER>NO</ANSWER>` — if **any** file is not read
"""


def extract_code_blocks(filepath: str | Path) -> str:
    text = Path(filepath).read_text(encoding="utf-8")
    pattern = re.compile(r"<code>.*?</code>", re.DOTALL)
    matches = pattern.findall(text)

    return "\n\n".join(matches)


def build_prompt_algo(clss_or_df, f1_norm, f2_norm):
    return f"""Determine whether the two {clss_or_df} in the two programs below have:
1. the same time complexity, and
2. the same behavior (semantic equivalence).

<PROGRAM_1>
{f1_norm}
</PROGRAM_1>

<PROGRAM_2>
{f2_norm}
</PROGRAM_2>
"""


def build_prompt_READ(file_list: list[str], run_history: str):
    if len(file_list) == 1:
        file = "the file " + f"`{file_list[0]}`" + " is"
    else:
        file = "the files" + ", ".join(list(map(lambda x: f"`{x}`", file_list))) + " are"

    return f"""Determine whether {file} read in the code blocks below:

{extract_code_blocks(run_history)}
"""