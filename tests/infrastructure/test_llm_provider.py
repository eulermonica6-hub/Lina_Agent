import json
from pathlib import Path
from typing import cast

import httpx
import pytest
from pydantic import SecretStr

from lina_agent.infrastructure.llm_provider import (
    EconomicLLMRouter,
    LLMMessage,
    LLMProviderName,
    LLMRequest,
    LLMResult,
    LLMSettings,
    OpenAICompatibleLLM,
    ProviderConfigurationError,
    ProviderExhaustedError,
    ProviderRequestError,
    ProviderResponseError,
    ResolvedProviderConfig,
    build_economic_router,
    build_llm_provider,
    resolve_provider_config,
    resolve_provider_configs,
)


def _settings(**values: object) -> LLMSettings:
    return LLMSettings.model_validate({"allow_paid_fallback": False, **values})


def _config(model: str = "test-model") -> ResolvedProviderConfig:
    return ResolvedProviderConfig(
        provider=LLMProviderName.GROQ,
        model=model,
        base_url="https://provider.example/v1/",
        api_key=SecretStr("gsk_test-secret"),
        cost_tier="free_quota",
    )


def _request() -> LLMRequest:
    return LLMRequest(messages=(LLMMessage(role="user", content="分析技能"),))


def test_auto_selection_prefers_first_groq_key_without_exposing_it(tmp_path: Path) -> None:
    key_file = tmp_path / "keys.txt"
    key_file.write_text(
        "deepseek=sk-deepseek\nnvidia=nvapi-nvidia\ngroq=gsk_first\ngsk_second\ngsk_first\nagnes=sk-agnes",
        encoding="utf-8",
    )

    config = resolve_provider_config(_settings(key_file=key_file))

    assert config.provider is LLMProviderName.GROQ
    assert config.model == "qwen/qwen3.6-27b"
    assert config.cost_tier == "free_quota"
    assert config.api_key.get_secret_value() == "gsk_first"
    assert "gsk_first" not in repr(config)

    configs = resolve_provider_configs(_settings(key_file=key_file))
    assert [item.provider for item in configs] == [
        LLMProviderName.GROQ,
        LLMProviderName.GROQ,
        LLMProviderName.AGNES,
        LLMProviderName.NVIDIA,
    ]
    assert configs[1].api_key.get_secret_value() == "gsk_second"
    assert configs[2].model == "agnes-2.5-flash"


def test_explicit_environment_key_overrides_file_and_selects_nvidia(tmp_path: Path) -> None:
    config = resolve_provider_config(
        _settings(
            provider="nvidia",
            key_file=tmp_path / "missing.txt",
            nvidia_api_key=SecretStr("nvapi-environment"),
            nvidia_model="openai/gpt-oss-20b",
        )
    )

    assert config.provider is LLMProviderName.NVIDIA
    assert config.model == "openai/gpt-oss-20b"
    assert config.base_url == "https://integrate.api.nvidia.com/v1"


def test_paid_deepseek_requires_explicit_opt_in(tmp_path: Path) -> None:
    key_file = tmp_path / "keys.txt"
    key_file.write_text("deepseek=sk-paid", encoding="utf-8")

    with pytest.raises(ProviderConfigurationError, match="付费 DeepSeek"):
        resolve_provider_config(_settings(key_file=key_file))

    config = resolve_provider_config(_settings(key_file=key_file, allow_paid_fallback=True))

    assert config.provider is LLMProviderName.DEEPSEEK
    assert config.model == "deepseek-v4-flash"
    assert config.cost_tier == "paid"

    configs = resolve_provider_configs(_settings(key_file=key_file, allow_paid_fallback=True))
    assert [item.provider for item in configs] == [LLMProviderName.DEEPSEEK]


def test_reports_missing_explicit_or_automatic_provider_keys(tmp_path: Path) -> None:
    missing = tmp_path / "missing.txt"

    with pytest.raises(ProviderConfigurationError, match="groq API key"):
        resolve_provider_config(_settings(provider="groq", key_file=missing))
    with pytest.raises(ProviderConfigurationError, match="Groq、Agnes 或 NVIDIA"):
        resolve_provider_config(_settings(key_file=missing))


def test_reports_invalid_utf8_key_file_without_echoing_content(tmp_path: Path) -> None:
    key_file = tmp_path / "keys.txt"
    key_file.write_bytes(b"\xffsecret")

    with pytest.raises(ProviderConfigurationError, match="无法读取 LLM key 文件"):
        resolve_provider_config(_settings(key_file=key_file))


def test_default_settings_and_provider_builder_do_not_require_global_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LINA_LLM_GROQ_API_KEY", raising=False)
    monkeypatch.delenv("LINA_LLM_AGNES_API_KEY", raising=False)
    monkeypatch.delenv("LINA_LLM_NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("LINA_LLM_DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(ProviderConfigurationError, match="Groq、Agnes 或 NVIDIA"):
        resolve_provider_config()

    provider = build_llm_provider(
        _settings(groq_api_key=SecretStr("gsk_test"), key_file=tmp_path / "missing")
    )
    assert isinstance(provider, OpenAICompatibleLLM)
    router = build_economic_router(
        _settings(groq_api_key=SecretStr("gsk_test"), key_file=tmp_path / "missing")
    )
    assert isinstance(router, EconomicLLMRouter)


def test_openai_compatible_provider_sends_safe_request_and_parses_usage() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://provider.example/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer gsk_test-secret"
        payload = cast(dict[str, object], json.loads(request.content))
        assert payload["model"] == "test-model"
        assert payload["temperature"] == 0.1
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "结构化结果"}}],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 4,
                    "total_tokens": 14,
                },
            },
        )

    provider = OpenAICompatibleLLM(_config(), transport=httpx.MockTransport(handler))

    result = provider.complete(_request())

    assert result.provider is LLMProviderName.GROQ
    assert result.content == "结构化结果"
    assert result.usage.total_tokens == 14


def test_groq_qwen_request_enables_json_mode_and_disables_reasoning() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = cast(dict[str, object], json.loads(request.content))
        assert payload["response_format"] == {"type": "json_object"}
        assert payload["reasoning_effort"] == "none"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "{}"}}]},
        )

    provider = OpenAICompatibleLLM(
        _config(model="qwen/qwen3.6-27b"),
        transport=httpx.MockTransport(handler),
    )
    request = LLMRequest(
        messages=(LLMMessage(role="user", content="JSON"),),
        response_format="json_object",
        reasoning_effort="none",
    )

    assert provider.complete(request).content == "{}"


@pytest.mark.parametrize(
    "config",
    [
        _config(model="other-model"),
        ResolvedProviderConfig(
            provider=LLMProviderName.NVIDIA,
            model="qwen/qwen3.6-27b",
            base_url="https://provider.example/v1/",
            api_key=SecretStr("nvapi-test"),
            cost_tier="free_quota",
        ),
    ],
)
def test_non_qwen_or_non_groq_provider_omits_groq_only_options(
    config: ResolvedProviderConfig,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = cast(dict[str, object], json.loads(request.content))
        assert "response_format" not in payload or config.provider is LLMProviderName.GROQ
        assert "reasoning_effort" not in payload
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}]},
        )

    provider = OpenAICompatibleLLM(config, transport=httpx.MockTransport(handler))
    request = LLMRequest(
        messages=(LLMMessage(role="user", content="JSON"),),
        response_format="json_object",
        reasoning_effort="none",
    )

    assert provider.complete(request).content == "ok"


def test_openai_compatible_provider_handles_default_usage_and_http_errors() -> None:
    success = OpenAICompatibleLLM(
        _config(),
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={"choices": [{"message": {"content": "ok"}}]},
            )
        ),
    )
    assert success.complete(_request()).usage.total_tokens == 0

    failed = OpenAICompatibleLLM(
        _config(),
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(429, text="gsk_must_not_leak")
        ),
    )
    with pytest.raises(ProviderResponseError, match="HTTP 429") as caught:
        failed.complete(_request())
    assert "must_not_leak" not in str(caught.value)


def test_openai_compatible_provider_rejects_invalid_payload() -> None:
    provider = OpenAICompatibleLLM(
        _config(),
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={"choices": []})),
    )

    with pytest.raises(ProviderResponseError, match="无效响应结构"):
        provider.complete(_request())

    empty_content = OpenAICompatibleLLM(
        _config(),
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json={"choices": [{"message": {"content": ""}}]})
        ),
    )
    with pytest.raises(ProviderResponseError, match="无效响应结构"):
        empty_content.complete(_request())


def test_openai_compatible_provider_wraps_connection_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("gsk_must_not_leak", request=request)

    provider = OpenAICompatibleLLM(_config(), transport=httpx.MockTransport(handler))

    with pytest.raises(ProviderRequestError, match="无法连接 groq") as caught:
        provider.complete(_request())
    assert "must_not_leak" not in str(caught.value)


class _StubProvider:
    def __init__(
        self,
        result: LLMResult | Exception,
    ) -> None:
        self.result = result
        self.calls = 0

    def complete(self, request: LLMRequest) -> LLMResult:
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        assert request.messages
        return self.result


def test_economic_router_fails_over_only_for_transient_errors() -> None:
    expected = OpenAICompatibleLLM(
        _config(),
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
        ),
    ).complete(_request())
    limited = _StubProvider(ProviderResponseError("limited", status_code=429))
    healthy = _StubProvider(expected)

    result = EconomicLLMRouter((limited, healthy)).complete(_request())

    assert result == expected
    assert limited.calls == 1
    assert healthy.calls == 1

    unauthorized = _StubProvider(ProviderResponseError("revoked key", status_code=401))
    assert EconomicLLMRouter((unauthorized, healthy)).complete(_request()) == expected
    assert healthy.calls == 2

    invalid_payload = _StubProvider(ProviderResponseError("invalid payload"))
    assert EconomicLLMRouter((invalid_payload, healthy)).complete(_request()) == expected
    assert healthy.calls == 3

    invalid = _StubProvider(ProviderResponseError("bad request", status_code=400))
    untouched = _StubProvider(expected)
    with pytest.raises(ProviderResponseError, match="bad request"):
        EconomicLLMRouter((invalid, untouched)).complete(_request())
    assert untouched.calls == 0


def test_economic_router_reports_exhaustion_and_rejects_empty_configuration() -> None:
    with pytest.raises(ValueError, match="至少需要"):
        EconomicLLMRouter(())

    unavailable = _StubProvider(ProviderRequestError("offline"))
    failed = _StubProvider(ProviderResponseError("server error", status_code=503))
    with pytest.raises(ProviderExhaustedError, match="均暂时不可用"):
        EconomicLLMRouter((unavailable, failed)).complete(_request())
