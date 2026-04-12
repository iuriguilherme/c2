import pytest
import httpx
import respx

from agents.output import AgentOutput, AgentAction
from agents.providers.ollama import OllamaProvider
from agents.providers.openrouter import OpenRouterProvider


# ── Output schema ────────────────────────────────────────────────────────────

def test_agent_output_valid_action():
    out = AgentOutput(
        action=AgentAction(type="locomotion", parameters={"direction": "north", "distance": 10}),
        user_prompt_update=None,
    )
    assert out.action.type == "locomotion"


def test_agent_output_no_action():
    out = AgentOutput(action=None, user_prompt_update="I moved north.")
    assert out.action is None
    assert out.user_prompt_update == "I moved north."


def test_agent_output_parse_from_llm_json():
    raw = '{"action": {"type": "signal_emitter", "parameters": {"message": "hello", "radius": 50}}, "user_prompt_update": "I said hello."}'
    out = AgentOutput.model_validate_json(raw)
    assert out.action.type == "signal_emitter"


def test_agent_output_invalid_json_returns_none():
    result = AgentOutput.parse_llm_response("{bad json")
    assert result is None


def test_agent_output_action_validated_against_manifest():
    from neural.models import CapabilityManifest, ActionCapability
    manifest = CapabilityManifest(
        schema_version="1.0", agent_id="e-1", tick=1,
        actions={"locomotion": ActionCapability(available=True, activation=0.9)},
    )
    out_invalid = AgentOutput(action=AgentAction(type="fly", parameters={}))
    assert not out_invalid.is_valid_for_manifest(manifest)

    out_valid = AgentOutput(
        action=AgentAction(type="locomotion", parameters={"direction": "north"})
    )
    assert out_valid.is_valid_for_manifest(manifest)


def test_agent_output_none_action_is_invalid():
    # action=None must return False — prevents null responses from being cached
    from neural.models import CapabilityManifest
    manifest = CapabilityManifest(schema_version="1.0", agent_id="e-1", tick=1)
    out = AgentOutput(action=None)
    assert not out.is_valid_for_manifest(manifest)


# ── Ollama provider ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ollama_check_available_true():
    with respx.mock:
        respx.get("http://localhost:11434/api/tags").mock(
            return_value=httpx.Response(200, json={"models": [{"name": "llama3.2"}]})
        )
        provider = OllamaProvider(base_url="http://localhost:11434")
        assert await provider.check_available() is True


@pytest.mark.asyncio
async def test_ollama_uses_api_key_when_provided():
    with respx.mock:
        route = respx.get("http://localhost:11434/api/tags").mock(
            return_value=httpx.Response(200, json={"models": [{"name": "llama3.2"}]})
        )
        provider = OllamaProvider(base_url="http://localhost:11434", api_key="test-key")
        assert await provider.check_available() is True
        assert route.called
        assert route.calls.last.request.headers.get("Authorization") == "Bearer test-key"


@pytest.mark.asyncio
async def test_ollama_check_available_false_on_connection_error():
    with respx.mock:
        respx.get("http://localhost:11434/api/tags").mock(
            side_effect=httpx.ConnectError("refused")
        )
        provider = OllamaProvider(base_url="http://localhost:11434")
        assert await provider.check_available() is False


@pytest.mark.asyncio
async def test_ollama_available_models(monkeypatch, tmp_path):
    import json
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({"ollama_allowed_models": ["llama3.2", "mistral"]}))

    import os
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    monkeypatch.setattr("agents.providers.ollama.os.path.join", lambda *args: str(settings_file))
    try:
        with respx.mock:
            respx.get("http://localhost:11434/api/tags").mock(
                return_value=httpx.Response(
                    200, json={"models": [{"name": "llama3.2"}, {"name": "mistral"}, {"name": "other"}]}
                )
            )
            provider = OllamaProvider(base_url="http://localhost:11434")
            models = await provider.get_available_models()
            assert "llama3.2" in models
            assert "mistral" in models
            assert "other" not in models
    finally:
        os.chdir(original_cwd)


@pytest.mark.asyncio
async def test_ollama_available_models_empty_allowed(monkeypatch, tmp_path):
    import json
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({"ollama_allowed_models": []}))

    import os
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    monkeypatch.setattr("agents.providers.ollama.os.path.join", lambda *args: str(settings_file))
    try:
        with respx.mock:
            respx.get("http://localhost:11434/api/tags").mock(
                return_value=httpx.Response(
                    200, json={"models": [{"name": "llama3.2"}, {"name": "mistral"}]}
                )
            )
            provider = OllamaProvider(base_url="http://localhost:11434")
            models = await provider.get_available_models()
            assert len(models) == 0
    finally:
        os.chdir(original_cwd)


@pytest.mark.asyncio
async def test_ollama_available_models_missing_file_allowed(monkeypatch, tmp_path):
    import os
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    fake_path = str(tmp_path / "settings.json")
    monkeypatch.setattr("agents.providers.ollama.os.path.join", lambda *args: fake_path)
    # File does not exist here
    try:
        with respx.mock:
            respx.get("http://localhost:11434/api/tags").mock(
                return_value=httpx.Response(
                    200, json={"models": [{"name": "llama3.2"}, {"name": "mistral"}]}
                )
            )
            provider = OllamaProvider(base_url="http://localhost:11434")
            models = await provider.get_available_models()
            assert len(models) == 0
    finally:
        os.chdir(original_cwd)


@pytest.mark.asyncio
async def test_ollama_generate_streams_content():
    lines = (
        b'{"message": {"role": "assistant", "content": "Hello"}, "done": false}\n'
        b'{"message": {"role": "assistant", "content": " world"}, "done": true}\n'
    )
    with respx.mock:
        respx.post("http://localhost:11434/api/chat").mock(
            return_value=httpx.Response(200, content=lines)
        )
        provider = OllamaProvider(base_url="http://localhost:11434")
        chunks = []
        async for chunk in provider.generate(
            model="llama3.2",
            system_prompt="You are an entity.",
            user_prompt="What do you do?",
            manifest_json="{}",
        ):
            chunks.append(chunk)
    assert "".join(chunks) == "Hello world"
