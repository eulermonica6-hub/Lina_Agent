import re
from enum import StrEnum
from pathlib import Path
from typing import Literal, Protocol

import httpx
from pydantic import BaseModel, Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from lina_agent.domain.models import DomainModel


class LLMProviderName(StrEnum):
    AUTO = "auto"
    GROQ = "groq"
    NVIDIA = "nvidia"
    DEEPSEEK = "deepseek"


class LLMSettings(BaseSettings):
    provider: LLMProviderName = LLMProviderName.AUTO
    allow_paid_fallback: bool = False
    key_file: Path = Path("data/private/LLM api key.txt")
    groq_api_key: SecretStr | None = None
    nvidia_api_key: SecretStr | None = None
    deepseek_api_key: SecretStr | None = None
    groq_model: str = "qwen/qwen3.6-27b"
    nvidia_model: str = "qwen/qwen3-next-80b-a3b-instruct"
    deepseek_model: str = "deepseek-v4-flash"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="LINA_LLM_",
        extra="ignore",
    )


class ProviderConfigurationError(ValueError):
    """Raised when a safe provider cannot be selected from local configuration."""


class ProviderRequestError(RuntimeError):
    """Raised when an LLM request cannot reach the selected provider."""


class ProviderResponseError(RuntimeError):
    """Raised when an LLM provider returns an unsuccessful or invalid response."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ProviderExhaustedError(RuntimeError):
    """Raised after all configured economic providers fail transiently."""


class ResolvedProviderConfig(BaseModel):
    provider: LLMProviderName
    model: str = Field(min_length=1)
    base_url: str = Field(min_length=1)
    api_key: SecretStr
    cost_tier: Literal["free_quota", "paid"]


class LLMMessage(DomainModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)


class LLMRequest(DomainModel):
    messages: tuple[LLMMessage, ...] = Field(min_length=1)
    max_tokens: int = Field(default=1024, ge=1, le=8192)
    temperature: float = Field(default=0.1, gt=0, le=2)


class LLMUsage(DomainModel):
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)


class LLMResult(DomainModel):
    provider: LLMProviderName
    model: str = Field(min_length=1)
    content: str = Field(min_length=1)
    usage: LLMUsage


class LLMProvider(Protocol):
    def complete(self, request: LLMRequest) -> LLMResult: ...


_BASE_URLS = {
    LLMProviderName.GROQ: "https://api.groq.com/openai/v1",
    LLMProviderName.NVIDIA: "https://integrate.api.nvidia.com/v1",
    LLMProviderName.DEEPSEEK: "https://api.deepseek.com",
}
_KEY_PATTERNS = {
    LLMProviderName.GROQ: re.compile(r"gsk_[A-Za-z0-9_-]+"),
    LLMProviderName.NVIDIA: re.compile(r"nvapi-[A-Za-z0-9_-]+"),
    LLMProviderName.DEEPSEEK: re.compile(r"(?i:deepseek)[^\n]*?(?P<key>sk-[A-Za-z0-9_-]+)"),
}


def resolve_provider_config(settings: LLMSettings | None = None) -> ResolvedProviderConfig:
    return resolve_provider_configs(settings)[0]


def resolve_provider_configs(
    settings: LLMSettings | None = None,
) -> tuple[ResolvedProviderConfig, ...]:
    resolved_settings = settings or LLMSettings()
    keys = _load_key_file(resolved_settings.key_file)
    environment_keys = {
        LLMProviderName.GROQ: resolved_settings.groq_api_key,
        LLMProviderName.NVIDIA: resolved_settings.nvidia_api_key,
        LLMProviderName.DEEPSEEK: resolved_settings.deepseek_api_key,
    }
    keys.update(
        {provider: secret for provider, secret in environment_keys.items() if secret is not None}
    )

    if resolved_settings.provider is LLMProviderName.AUTO:
        selected = [
            provider
            for provider in (LLMProviderName.GROQ, LLMProviderName.NVIDIA)
            if provider in keys
        ]
        if resolved_settings.allow_paid_fallback and LLMProviderName.DEEPSEEK in keys:
            selected.append(LLMProviderName.DEEPSEEK)
    else:
        selected = [resolved_settings.provider]

    if not selected:
        if LLMProviderName.DEEPSEEK in keys:
            raise ProviderConfigurationError(
                "只检测到付费 DeepSeek key；请显式选择 deepseek 或允许付费回退。"
            )
        raise ProviderConfigurationError("没有检测到可用的 Groq 或 NVIDIA API key。")
    if selected[0] not in keys:
        raise ProviderConfigurationError(f"没有检测到 {selected[0].value} API key。")

    models = {
        LLMProviderName.GROQ: resolved_settings.groq_model,
        LLMProviderName.NVIDIA: resolved_settings.nvidia_model,
        LLMProviderName.DEEPSEEK: resolved_settings.deepseek_model,
    }
    return tuple(
        ResolvedProviderConfig(
            provider=provider,
            model=models[provider],
            base_url=_BASE_URLS[provider],
            api_key=keys[provider],
            cost_tier=("paid" if provider is LLMProviderName.DEEPSEEK else "free_quota"),
        )
        for provider in selected
    )


def _load_key_file(path: Path) -> dict[LLMProviderName, SecretStr]:
    if not path.is_file():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ProviderConfigurationError(f"无法读取 LLM key 文件：{path}") from error

    keys: dict[LLMProviderName, SecretStr] = {}
    for provider, pattern in _KEY_PATTERNS.items():
        match = pattern.search(text)
        if match is not None:
            value = match.groupdict().get("key") or match.group()
            keys[provider] = SecretStr(value)
    return keys


class _CompletionMessage(BaseModel):
    content: str = Field(min_length=1)


class _CompletionChoice(BaseModel):
    message: _CompletionMessage


class _CompletionUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class _CompletionPayload(BaseModel):
    choices: tuple[_CompletionChoice, ...] = Field(min_length=1)
    usage: _CompletionUsage = Field(default_factory=_CompletionUsage)


class OpenAICompatibleLLM:
    def __init__(
        self,
        config: ResolvedProviderConfig,
        *,
        timeout_seconds: float = 30,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._config = config
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    def complete(self, request: LLMRequest) -> LLMResult:
        payload = {
            "model": self._config.model,
            "messages": [message.model_dump(mode="json") for message in request.messages],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        headers = {
            "Authorization": f"Bearer {self._config.api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(
                timeout=self._timeout_seconds,
                transport=self._transport,
            ) as client:
                response = client.post(
                    f"{self._config.base_url.rstrip('/')}/chat/completions",
                    headers=headers,
                    json=payload,
                )
        except httpx.RequestError as error:
            raise ProviderRequestError(
                f"无法连接 {self._config.provider.value} 模型服务。"
            ) from error

        if response.is_error:
            raise ProviderResponseError(
                f"{self._config.provider.value} 模型服务返回 HTTP {response.status_code}。",
                status_code=response.status_code,
            )
        try:
            completion = _CompletionPayload.model_validate(response.json())
        except (ValueError, ValidationError) as error:
            raise ProviderResponseError(
                f"{self._config.provider.value} 返回了无效响应结构。"
            ) from error

        usage = completion.usage
        return LLMResult(
            provider=self._config.provider,
            model=self._config.model,
            content=completion.choices[0].message.content,
            usage=LLMUsage(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
            ),
        )


def build_llm_provider(settings: LLMSettings | None = None) -> OpenAICompatibleLLM:
    return OpenAICompatibleLLM(resolve_provider_config(settings))


class EconomicLLMRouter:
    def __init__(self, providers: tuple[LLMProvider, ...]) -> None:
        if not providers:
            raise ValueError("至少需要配置一个 LLM Provider")
        self._providers = providers

    def complete(self, request: LLMRequest) -> LLMResult:
        for provider in self._providers:
            try:
                return provider.complete(request)
            except ProviderRequestError:
                continue
            except ProviderResponseError as error:
                if error.status_code is not None and error.status_code not in {
                    408,
                    429,
                    500,
                    502,
                    503,
                    504,
                }:
                    raise
        raise ProviderExhaustedError("所有已配置模型服务均暂时不可用。")


def build_economic_router(settings: LLMSettings | None = None) -> EconomicLLMRouter:
    return EconomicLLMRouter(
        tuple(OpenAICompatibleLLM(config) for config in resolve_provider_configs(settings))
    )
