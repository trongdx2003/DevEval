import re
import time
import ast

from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI

from .prompts import (
    system_prompt_ALGO, system_prompt_IF,
    build_prompt_algo, build_prompt_IF
)

from utils import normalize

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="",
)


def get_openrouter_answer(
        user_prompt, model="google/gemini-3-flash-preview", max_tokens=4096,
        temperature=0.1, system_prompt="You are a helpful assistant!"):
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        max_completion_tokens=max_tokens,
        temperature=temperature
    )

    return completion.choices[0].message.content


def extract_dictionary(text):
    pattern = r"<ANSWER>\s*(.*?)\s*</ANSWER>"
    result = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if result:
        dictionary = result.group(1)
        try:
            return ast.literal_eval(dictionary)
        except Exception:
            # print("Cannot parse the dictionary")
            raise ValueError("Cannot parse the dictionary")

    raise ValueError("Cannot find the dictionary")


def get_judge_ALGO(
        src1, src2, focus, rm_print_args=True,
        max_call=3, wait_for_callback=3,
        model="google/gemini-3-flash-preview", max_tokens=4096,
        temperature=0.1, system_prompt=system_prompt_ALGO,
):
    try:
        # f1_norm, f2_norm = get_normalized_files(f1_path, f2_path, focus, rm_print_args=rm_print_args)
        with ThreadPoolExecutor() as ex:
            fut1 = ex.submit(normalize, src1, focus, rm_print_args)
            fut2 = ex.submit(normalize, src2, focus, rm_print_args)

            f1_norm = fut1.result()
            f2_norm = fut2.result()

    except Exception as e:
        print("-- Error when normalizing file:", e)
        return None

    split_names = focus.split(".")

    if len(split_names) > 1:
        _name = split_names[1]
        _classname = split_names[0]
        cls_or_df = f"methods `{_name}` of class {_classname}"
    else:
        cls_or_df = f"functions `{focus}`"

    user_prompt = build_prompt_algo(cls_or_df, f1_norm, f2_norm)

    for _ in range(max_call):
        answer = get_openrouter_answer(
            user_prompt=user_prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system_prompt=system_prompt
        )

        try:
            return_value = extract_dictionary(answer)
            print(f"Get judge ALGO for item `{focus}`")
            return return_value
        except Exception:
            time.sleep(wait_for_callback)

    print(f"Failed to get ALGO judge after {max_call} retries")

