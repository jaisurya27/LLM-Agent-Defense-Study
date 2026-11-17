"""Builds the agent for one episode: system message, model, tool loop.

The pipeline is the same as AgentDojo's standard one. The only differences
between defenses are the two hooks from src/defenses.py:
  * get_defense_instruction -> appended to the system message
  * format_external_content -> applied to each tool result's text

Attack text lives in the environment data, so it is already inside a tool
result when format_external_content runs: insertion happens before wrapping.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass, field

from agentdojo.agent_pipeline import AgentPipeline, InitQuery, SystemMessage, ToolsExecutionLoop, ToolsExecutor
from agentdojo.agent_pipeline.agent_pipeline import load_system_message
from agentdojo.agent_pipeline.base_pipeline_element import BasePipelineElement
from agentdojo.agent_pipeline.tool_execution import tool_result_to_str
from agentdojo.functions_runtime import EmptyEnv, Env, FunctionsRuntime
from agentdojo.logging import Logger
from agentdojo.types import ChatAssistantMessage, ChatMessage, text_content_block_from_string

from src.defenses import format_external_content, get_defense_instruction


@dataclass
class UsageMeter:
    """Adds up token usage over every model call in one episode."""

    calls: list[dict] = field(default_factory=list)

    def add(self, input_tokens: int | None, output_tokens: int | None) -> None:
        self.calls.append({"input_tokens": input_tokens, "output_tokens": output_tokens})

    def total(self, key: str) -> int | None:
        values = [c[key] for c in self.calls]
        if not values or any(v is None for v in values):
            return None  # unknown stays null rather than a guessed number
        return sum(values)


class CaptureLogger(Logger):
    """Keeps the latest message list, so a trace survives a crash mid-episode."""

    def __init__(self) -> None:
        self.attempts: list[list[ChatMessage]] = []
        self.logdir = None

    def new_attempt(self) -> None:
        self.attempts.append([])

    def log(self, messages: Sequence[ChatMessage], **kwargs) -> None:
        if not self.attempts:
            self.attempts.append([])
        self.attempts[-1] = list(messages)

    def log_error(self, *args, **kwargs) -> None:
        pass


class RecordingPipeline(AgentPipeline):
    """AgentDojo may call the pipeline again if the model returns no output.
    Each call is kept as a separate attempt in the trace."""

    def query(self, query, runtime, env=EmptyEnv(), messages=[], extra_args={}):
        logger = Logger.get()
        if isinstance(logger, CaptureLogger):
            logger.new_attempt()
        return super().query(query, runtime, env, messages, extra_args)


def build_system_message(defense: str) -> str:
    """AgentDojo's default system message, plus the defense instruction if any."""
    base = load_system_message(None).rstrip("\n")
    instruction = get_defense_instruction(defense)
    return f"{base}\n\n{instruction}" if instruction else base


def build_pipeline(defense: str, llm: BasePipelineElement, max_tool_iterations: int) -> RecordingPipeline:
    def formatter(tool_result) -> str:
        return format_external_content(tool_result_to_str(tool_result), defense)

    tools_loop = ToolsExecutionLoop([ToolsExecutor(formatter), llm], max_iters=max_tool_iterations)
    pipeline = RecordingPipeline([SystemMessage(build_system_message(defense)), InitQuery(), llm, tools_loop])
    pipeline.name = f"{getattr(llm, 'model', 'model')}-{defense}"
    return pipeline


# ---------------------------------------------------------------- models

def build_llm(model_cfg: dict, meter: UsageMeter) -> BasePipelineElement:
    """Create the model element and attach token counting."""
    provider = model_cfg["provider"]
    temperature = model_cfg.get("temperature")

    if provider in ("openai", "openai_compatible"):
        import openai
        from agentdojo.agent_pipeline.llms.openai_llm import OpenAILLM

        if provider == "openai":
            client = openai.OpenAI()
        else:
            client = openai.OpenAI(base_url=model_cfg["base_url"], api_key=os.environ[model_cfg["api_key_env"]])
        original_create = client.chat.completions.create

        def create(*args, **kwargs):
            # AgentDojo 0.1.35 sends `temperature or NOT_GIVEN`, so a configured
            # 0.0 is dropped and the API default (1.0) is used. Set it here so
            # the decoding setting in the config is the one that is applied.
            if temperature is not None:
                kwargs["temperature"] = temperature
            response = original_create(*args, **kwargs)
            usage = getattr(response, "usage", None)
            meter.add(getattr(usage, "prompt_tokens", None), getattr(usage, "completion_tokens", None))
            return response

        client.chat.completions.create = create
        return OpenAILLM(client, model_cfg["model_id"], temperature=temperature)

    if provider == "anthropic":
        import anthropic
        from agentdojo.agent_pipeline.llms import anthropic_llm

        class MeteredAnthropicLLM(anthropic_llm.AnthropicLLM):
            def query(self, query, runtime, env=EmptyEnv(), messages=[], extra_args={}):
                original = anthropic_llm.chat_completion_request

                async def metered(*args, **kwargs):
                    message = await original(*args, **kwargs)
                    meter.add(message.usage.input_tokens, message.usage.output_tokens)
                    return message

                anthropic_llm.chat_completion_request = metered
                try:
                    return super().query(query, runtime, env, messages, extra_args)
                finally:
                    anthropic_llm.chat_completion_request = original

        return MeteredAnthropicLLM(
            anthropic.AsyncAnthropic(),
            model_cfg["model_id"],
            temperature=temperature,
            max_tokens=model_cfg.get("max_output_tokens") or 1024,
        )

    raise ValueError(f"Unknown model provider {provider!r}")


class ScriptedLLM(BasePipelineElement):
    """Offline stand-in for a model. Makes no API call.

    Replays the task's reference tool calls one per turn through the real
    pipeline, so prompts, tool formatting, traces and evaluators can be checked
    without a key or any spending. With `injection_task` set it first carries
    out the attacker's goal, which exercises the attack-success path.
    Its outcomes say nothing about how a real model behaves.
    """

    model = "offline-scripted"

    def __init__(self, user_task, injection_task=None) -> None:
        self.user_task = user_task
        self.injection_task = injection_task
        self.script = None

    def query(
        self,
        query: str,
        runtime: FunctionsRuntime,
        env: Env = EmptyEnv(),
        messages: Sequence[ChatMessage] = [],
        extra_args: dict = {},
    ):
        if self.script is None:
            snapshot = env.model_copy(deep=True)
            calls = list(self.injection_task.ground_truth(snapshot)) if self.injection_task else []
            self.script = calls + list(self.user_task.ground_truth(snapshot))
        if self.script:
            call = self.script.pop(0)
            reply = ChatAssistantMessage(role="assistant", content=[text_content_block_from_string("")], tool_calls=[call])
        else:
            text = self.user_task.GROUND_TRUTH_OUTPUT or "Done."
            reply = ChatAssistantMessage(role="assistant", content=[text_content_block_from_string(text)], tool_calls=None)
        return query, runtime, env, [*messages, reply], extra_args
