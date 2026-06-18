import json
import logging
import time
from typing import AsyncGenerator

import anthropic

try:
    from backend.agent.system_prompt import build_system_prompt
    from backend.agent.tools import TOOLS
    from backend.agent.tool_handlers import handle_tool_call
except ModuleNotFoundError:
    from agent.system_prompt import build_system_prompt
    from agent.tools import TOOLS
    from agent.tool_handlers import handle_tool_call

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("halda")

MODEL = "claude-sonnet-4-6"
MAX_TOOL_ROUNDS = 10

client = anthropic.Anthropic()


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _serialize_block(block) -> dict:
    if block.type == "text":
        return {"type": "text", "text": block.text}
    elif block.type == "tool_use":
        return {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
    return block.model_dump()


async def run_conversation(
    student_id: str,
    user_message: str,
    profile: dict,
    history: list,
) -> tuple[str, dict, list]:
    system = build_system_prompt(profile)
    history.append({"role": "user", "content": user_message})

    log.info("[%s] Starting conversation. Message: %s", student_id, user_message[:80])

    all_text_parts = []

    for round_num in range(MAX_TOOL_ROUNDS):
        log.info("[%s] Round %d — calling Claude...", student_id, round_num + 1)
        t0 = time.time()

        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system,
            messages=history,
            tools=TOOLS,
        )

        elapsed = time.time() - t0
        log.info(
            "[%s] Round %d — got response in %.1fs. stop_reason=%s, blocks=%d, usage=%s",
            student_id, round_num + 1, elapsed, response.stop_reason,
            len(response.content),
            f"in={response.usage.input_tokens} out={response.usage.output_tokens}",
        )

        for block in response.content:
            if block.type == "text" and block.text.strip():
                all_text_parts.append(block.text)

        assistant_content = [_serialize_block(block) for block in response.content]
        history.append({"role": "assistant", "content": assistant_content})

        if response.stop_reason != "tool_use":
            break

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            log.info("[%s]   Tool call: %s(%s)", student_id, block.name, str(block.input)[:120])
            result_str, updated_profile = handle_tool_call(block.name, block.input, profile)
            if updated_profile is not profile:
                profile.clear()
                profile.update(updated_profile)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result_str,
            })

        if tool_results:
            history.append({"role": "user", "content": tool_results})

        system = build_system_prompt(profile)

    response_text = "\n\n".join(all_text_parts)

    log.info("[%s] Done. Response length: %d chars", student_id, len(response_text))
    return response_text, profile, history


async def stream_conversation(
    student_id: str,
    user_message: str,
    profile: dict,
    history: list,
) -> AsyncGenerator[str, None]:
    system = build_system_prompt(profile)
    history.append({"role": "user", "content": user_message})

    log.info("[%s] Starting stream. Message: %s", student_id, user_message[:80])

    for round_num in range(MAX_TOOL_ROUNDS):
        log.info("[%s] Round %d — streaming from Claude...", student_id, round_num + 1)
        t0 = time.time()

        with client.messages.stream(
            model=MODEL,
            max_tokens=4096,
            system=system,
            messages=history,
            tools=TOOLS,
        ) as stream:
            for event in stream:
                if (
                    event.type == "content_block_delta"
                    and event.delta.type == "text_delta"
                ):
                    yield _sse("text_delta", {"text": event.delta.text})

            response = stream.get_final_message()

        elapsed = time.time() - t0
        log.info(
            "[%s] Round %d — done in %.1fs. stop_reason=%s, blocks=%d",
            student_id, round_num + 1, elapsed, response.stop_reason,
            len(response.content),
        )

        assistant_content = [_serialize_block(block) for block in response.content]
        history.append({"role": "assistant", "content": assistant_content})

        if response.stop_reason != "tool_use":
            break

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            log.info("[%s]   Tool call: %s(%s)", student_id, block.name, str(block.input)[:120])
            result_str, updated_profile = handle_tool_call(block.name, block.input, profile)
            if updated_profile is not profile:
                profile.clear()
                profile.update(updated_profile)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result_str,
            })
            yield _sse("tool_call", {"tool": block.name})

        yield _sse("profile_update", {"updated_profile": profile})

        if tool_results:
            history.append({"role": "user", "content": tool_results})

        system = build_system_prompt(profile)

    yield _sse("done", {"updated_profile": profile})
    log.info("[%s] Stream complete.", student_id)
