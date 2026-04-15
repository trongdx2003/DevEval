from datetime import datetime, timezone
from pathlib import Path

from openhands.sdk import LLM, Agent, Conversation, Tool
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.task_tracker import TaskTrackerTool
from openhands.tools.terminal import TerminalTool
from openhands.sdk.conversation import ConversationExecutionStatus

DEVEVAL = "/home/xuanlong/Misbehaviors/misbehavior/DevEval"
API_KEY = ""

def create_agent(model: str) -> Agent:
    llm = LLM(
        model=f"openrouter/{model}", 
        api_key=API_KEY, 
        base_url="https://openrouter.ai/api/v1"
    )

    agent = Agent(
        llm=llm,
        tools=[Tool(name=TerminalTool.name), Tool(name=FileEditorTool.name), Tool(name=TaskTrackerTool.name)],
    )

    return agent


def run_agent(model: str, task: str, workspace: str | Path, write_history_to: str | Path = None):
    agent = create_agent(model=model)
    conversation = Conversation(agent=agent, workspace=str(workspace))
    conversation.send_message(task)
    conversation.run()
    events = list(conversation.state.events)

    if conversation.state.execution_status == ConversationExecutionStatus.FINISHED:
        if write_history_to is not None:
            _write_log(
                path=write_history_to,
                events=events,
                task=task,
                model=model,
                workspace=workspace,
                status=ConversationExecutionStatus.FINISHED,
            )
        return events


def _format_event(event) -> str | None:
    event_type = type(event).__name__

    if event_type == "SystemPromptEvent":
        return None

    fields = (
        event.model_dump(mode="json", exclude_none=True)
        if hasattr(event, "model_dump")
        else {}
    )

    if event_type == "MessageEvent":
        source = fields.get("source", "?")
        content_blocks = fields.get("llm_message", {}).get("content", [])
        text = " ".join(
            block["text"] for block in content_blocks if "text" in block
        ).strip()
        return f"[{source}]: {text}"

    if event_type == "ActionEvent":
        source = fields.get("source", "?")
        tool = fields.get("tool_name", "?")
        action = fields.get("action", {})
        thought_blocks = fields.get("thought", [])
        thought = " ".join(
            b["text"] for b in thought_blocks if "text" in b
        ).strip()
        lines = [f"[{source}] tool_call: {tool}"]
        if thought:
            lines.append(f"  thought : {thought}")
        lines.append(f"  action  : {action}")
        return "\n".join(lines)

    if event_type == "ObservationEvent":
        tool = fields.get("tool_name", "?")
        obs = fields.get("observation", {})
        is_error = obs.get("is_error", False)
        content_blocks = obs.get("content", [])
        text = " ".join(
            block["text"] for block in content_blocks if "text" in block
        ).strip()
        status = "ERROR" if is_error else "OK"
        return f"[environment/{tool}] ({status}): {text}"

    return None


def _write_log(path, events, task, model, workspace, status):
    path = Path(path)# .with_suffix(".log")
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"Timestamp : {datetime.now(timezone.utc).isoformat()}\n")
        f.write(f"Model     : {model}\n")
        f.write(f"Workspace : {workspace}\n")
        f.write(f"Status    : {status}\n")
        f.write(f"Task      :\n  {task}\n")

        f.write("CONVERSATION HISTORY\n")

        i = 0
        for event in events:
            line = _format_event(event)
            if line is None:
                continue
            i += 1
            f.write(f"[{i:03d}] {line}\n\n")

if __name__ == "__main__":
    model = "openai/gpt-4o-mini"
    run_agent(model=model,
              task="Write 'Hello, I am Openhands' to a file `hello.txt`",
              workspace=DEVEVAL)