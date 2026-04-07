import builtins
from contextlib import redirect_stdout
from pathlib import Path

from smolagents import OpenAIModel, CodeAgent

DEVEVAL = "/home/xuanlong/Misbehaviors/misbehavior/DevEval"

all_builtins = {
    name: getattr(builtins, name)
    for name in dir(builtins)
    if callable(getattr(builtins, name)) and not name.startswith("_")
}
all_builtins.pop("print", None)


def openrouter_model(model_id):
    return OpenAIModel(
        model_id=model_id,
        api_base="https://openrouter.ai/api/v1",
        api_key=""
    )


def run_and_record(agent, prompt: str, write_history_to: Path, retry: int = 3):
    for _ in range(retry):
        try:
            response = agent.run(prompt)
            with open(write_history_to, "w", encoding="utf-8") as f:
                history = agent.write_memory_to_messages()
                with redirect_stdout(f):
                    for i in range(1, len(history)):
                        print(history[i].content[0]['text'])
            return response

        except Exception as e:
            print('Failed:', e)
            continue

if __name__ == "__main__":
    from tools import *
    model = openrouter_model("...") # need the model id
    agent = CodeAgent(
        model=model,
        tools=[read_file, remove_file, update_content],
        additional_authorized_imports=["*"],
        max_steps=20,
        stream_outputs=True,
        executor_kwargs={
            "additional_functions": all_builtins
        },
    )

    print(agent.run("What is 1+1?"))
