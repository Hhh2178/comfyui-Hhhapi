import json
import time

from . import provider_store
from .adapters import get_adapter
from .secret_store import resolve_api_key
from .utils.response import dumps, error_payload


def _channel_label(adapter_protocol, has_image):
    if adapter_protocol == "minimax_cli_vision":
        return "MiniMax识图通道"
    if has_image:
        return "视觉文本通道"
    return "文本通道"


def _should_retry_text_error(exc):
    text = str(exc or "").lower()
    retry_markers = (
        "http 429",
        "http 529",
        "rate limit",
        "too many requests",
        "overloaded",
        "server is busy",
        "service unavailable",
        "temporarily unavailable",
        "访问繁忙",
        "请求过多",
        "服务繁忙",
        "稍后重试",
        "超载",
    )
    return any(marker in text for marker in retry_markers)


class HhhapiText:
    @classmethod
    def INPUT_TYPES(cls):
        providers = provider_store.provider_ids("text")
        provider_id = providers[0]
        models = provider_store.model_names(provider_id=provider_id, task_type="text")
        return {
            "required": {
                "服务商": (providers, {"default": provider_id}),
                "模型": (models, {"default": models[0]}),
                "系统提示词": ("STRING", {"default": "You are a helpful assistant.", "multiline": True}),
                "用户提示词": ("STRING", {"default": "", "multiline": True}),
                "温度": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.1}),
                "最大Token数": ("INT", {"default": 50000, "min": 1, "max": 262144, "step": 1}),
                "随机种子": ("INT", {"default": -1, "min": -1, "max": 0xFFFFFFFFFFFFFFFF}),
                "响应格式": (["文本", "JSON对象"], {"default": "文本"}),
                "超时秒数": ("INT", {"default": 120, "min": 1, "max": 3600, "step": 1}),
            },
            "optional": {
                "参考图片": ("IMAGE",),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("文本", "响应JSON", "用量JSON", "思考链")
    FUNCTION = "run"
    CATEGORY = "Hhh/文本API"

    @classmethod
    def VALIDATE_INPUTS(cls, **kwargs):
        return True

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    def run(self, 服务商="", 模型="", 系统提示词="", 用户提示词="", 温度=0.7, 最大Token数=50000, 随机种子=-1, 响应格式="文本", 超时秒数=120, 参考图片=None):
        parsed = {}
        adapter_protocol = ""
        try:
            parsed = provider_store.build_text_runtime_config(服务商, 模型, 超时秒数)
            if parsed.get("task_type") != "text":
                raise ValueError("Provider task_type must be text")
            if 参考图片 is not None and "vision_input" not in parsed.get("capabilities", []):
                raise ValueError(
                    f"当前模型不支持参考图片输入: provider={parsed.get('provider_id', '')}, model={parsed.get('model', '')}. "
                    "请为该模型关闭参考图片，或为支持视觉输入的模型开启 vision_input 能力。"
                )
            api_key = resolve_api_key(parsed)
            if not api_key:
                raise ValueError("API key not found. Set it in Hhh 文本API服务商管理.")
            adapter_protocol = parsed.get("protocol", "")
            if 参考图片 is not None and "minimax_understand_image" in parsed.get("capabilities", []):
                adapter_protocol = "minimax_cli_vision"
            adapter = get_adapter(adapter_protocol)
            max_attempts = 3
            attempt = 0
            while attempt < max_attempts:
                attempt += 1
                try:
                    result = adapter.call_text(
                        parsed,
                        api_key,
                        系统提示词,
                        用户提示词,
                        温度,
                        最大Token数,
                        随机种子,
                        "json_object" if 响应格式 == "JSON对象" else "text",
                        ref_image=参考图片,
                    )
                    result["channel"] = adapter_protocol
                    result["channel_label"] = _channel_label(adapter_protocol, 参考图片 is not None)
                    result["attempts"] = attempt
                    return (
                        result.get("text", ""),
                        dumps(result),
                        dumps(result.get("usage", {})),
                        result.get("reasoning", ""),
                    )
                except Exception as exc:
                    if attempt >= max_attempts or not _should_retry_text_error(exc):
                        raise
                    time.sleep(min(1.5 * attempt, 4.0))
        except Exception as exc:
            error = error_payload("text_api_error", str(exc), parsed)
            if adapter_protocol:
                error["channel"] = adapter_protocol
                error["channel_label"] = _channel_label(adapter_protocol, 参考图片 is not None)
            return ("", dumps(error), "{}", "")
