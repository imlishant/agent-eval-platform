"""Model adapter registry. A new provider protocol = one class + one line here.
A new model on an existing protocol = only a config file."""

from ..schema import ModelSpec
from .base import ModelAdapter, ModelOutputError, ModelResponse, ProviderError, ToolCall
from .openai_compat import OpenAICompatAdapter

MODEL_ADAPTERS: dict[str, type[ModelAdapter]] = {
    "openai_compat": OpenAICompatAdapter,
}


def get_model(spec: ModelSpec) -> ModelAdapter:
    if spec.provider not in MODEL_ADAPTERS:
        raise ValueError(f"unknown model provider '{spec.provider}'. Known: {sorted(MODEL_ADAPTERS)}")
    return MODEL_ADAPTERS[spec.provider](spec)


__all__ = ["ModelAdapter", "ModelOutputError", "ModelResponse", "ProviderError", "ToolCall", "get_model"]
