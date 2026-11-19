import asyncio
from types import SimpleNamespace

from agents import Runner

from web.runtime import MockRuntime, OpenAIRuntime


def test_sdk_runtime_uses_structured_output_and_records_usage(monkeypatch):
    async def simulate_runner(agent, prompt, *, max_turns, run_config):
        assert agent.output_type.__name__ == "Objective"
        assert agent.tools == []
        assert max_turns == 1 and run_config.tracing_disabled
        assert agent.model_settings.store is False
        assert '"language": "en"' in prompt
        return SimpleNamespace(final_output={"test": "SDK adapter fixture"}, context_wrapper=SimpleNamespace(
            usage=SimpleNamespace(input_tokens=55, output_tokens=19, total_tokens=74, requests=1)))

    monkeypatch.setattr(Runner, "run", simulate_runner)
    result = asyncio.run(OpenAIRuntime("gpt-4.1-mini").call("define", {"assessment": {"language": "en"}}))
    assert result.model == "gpt-4.1-mini"
    assert result.usage == {"input_tokens": 55, "output_tokens": 19, "total_tokens": 74, "requests": 1}
    assert MockRuntime.model == "mock-simulation"
