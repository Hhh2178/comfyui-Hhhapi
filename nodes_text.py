import json
import time

from . import provider_store
from .adapters import get_adapter
from .secret_store import resolve_api_key
from .utils.response import dumps, error_payload


def _channel_label(adapter_protocol, has_image, visual_mode="自动"):
    if adapter_protocol == "minimax_cli_vision":
        if visual_mode == "二段式整理输出":
            return "MiniMax二段式通道"
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


def _build_minimax_direct_prompt(system_prompt, user_prompt):
    parts = []
    if (system_prompt or "").strip():
        parts.append(f"[系统要求]\n{system_prompt.strip()}")
    if (user_prompt or "").strip():
        parts.append(f"[用户要求]\n{user_prompt.strip()}")
    if not parts:
        return "请分析这张图片，并直接输出最终结果。"
    parts.append("请严格遵守以上要求，只输出最终结果，不要输出分析过程，不要解释你是如何观察到这些内容的。")
    return "\n\n".join(parts)


def _build_vision_extraction_prompt(user_prompt):
    base = [
        "请先只做图像事实提取。",
        "只描述图片中可以直接观察到的视觉事实，不要推测设定，不要做审美评价，不要输出创作建议。",
        "请尽量覆盖：主体形象、姿态动作、表情、服饰/材质、构图、场景、背景、文字元素、边框/版式、颜色和风格线索。",
    ]
    if (user_prompt or "").strip():
        base.append(f"后续用户目标如下，请提取与其相关的视觉事实：\n{user_prompt.strip()}")
    base.append("请用简洁条目或短段落输出视觉事实。")
    return "\n\n".join(base)


def _build_stage2_prompt(vision_facts, user_prompt):
    parts = [
        "下面是从参考图片中提取出的视觉事实，请基于这些事实完成最终输出。",
        "只输出最终结果，不要重复分析过程，不要解释你是如何观察到图片的。",
        f"[视觉事实]\n{(vision_facts or '').strip()}",
    ]
    if (user_prompt or "").strip():
        parts.append(f"[用户要求]\n{user_prompt.strip()}")
    return "\n\n".join(parts)


def _call_with_retry(adapter, config, api_key, system_prompt, prompt, temperature, max_tokens, seed, response_format, ref_image=None):
    max_attempts = 3
    attempt = 0
    while attempt < max_attempts:
        attempt += 1
        try:
            result = adapter.call_text(
                config,
                api_key,
                system_prompt,
                prompt,
                temperature,
                max_tokens,
                seed,
                response_format,
                ref_image=ref_image,
            )
            return result, attempt
        except Exception as exc:
            if attempt >= max_attempts or not _should_retry_text_error(exc):
                raise
            time.sleep(min(1.5 * attempt, 4.0))


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
                "视觉结果模式": (["自动", "直接识图输出", "二段式整理输出"], {"default": "自动"}),
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

    def run(self, 服务商="", 模型="", 系统提示词="", 用户提示词="", 视觉结果模式="自动", 温度=0.7, 最大Token数=50000, 随机种子=-1, 响应格式="文本", 超时秒数=120, 参考图片=None):
        parsed = {}
        adapter_protocol = ""
        effective_visual_mode = 视觉结果模式 or "自动"
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
            response_format = "json_object" if 响应格式 == "JSON对象" else "text"

            if adapter_protocol == "minimax_cli_vision":
                if effective_visual_mode == "自动":
                    effective_visual_mode = "二段式整理输出"

                if effective_visual_mode == "直接识图输出":
                    direct_prompt = _build_minimax_direct_prompt(系统提示词, 用户提示词)
                    result, attempts = _call_with_retry(
                        adapter,
                        parsed,
                        api_key,
                        "",
                        direct_prompt,
                        温度,
                        最大Token数,
                        随机种子,
                        response_format,
                        ref_image=参考图片,
                    )
                    result["channel"] = adapter_protocol
                    result["channel_label"] = _channel_label(adapter_protocol, True, effective_visual_mode)
                    result["visual_mode"] = effective_visual_mode
                    result["attempts"] = attempts
                    return (
                        result.get("text", ""),
                        dumps(result),
                        dumps(result.get("usage", {})),
                        result.get("reasoning", ""),
                    )

                vision_prompt = _build_vision_extraction_prompt(用户提示词)
                stage1_result, stage1_attempts = _call_with_retry(
                    adapter,
                    parsed,
                    api_key,
                    "",
                    vision_prompt,
                    0.2,
                    最大Token数,
                    随机种子,
                    "text",
                    ref_image=参考图片,
                )
                vision_facts = stage1_result.get("text", "").strip()
                if not vision_facts:
                    raise RuntimeError("MiniMax 识图阶段没有返回可用的视觉事实。")

                text_adapter = get_adapter(parsed.get("protocol", ""))
                stage2_prompt = _build_stage2_prompt(vision_facts, 用户提示词)
                stage2_result, stage2_attempts = _call_with_retry(
                    text_adapter,
                    parsed,
                    api_key,
                    系统提示词,
                    stage2_prompt,
                    温度,
                    最大Token数,
                    随机种子,
                    response_format,
                    ref_image=None,
                )
                merged_usage = {
                    "stage1": stage1_result.get("usage", {}),
                    "stage2": stage2_result.get("usage", {}),
                }
                merged_result = {
                    **stage2_result,
                    "channel": adapter_protocol,
                    "channel_label": _channel_label(adapter_protocol, True, effective_visual_mode),
                    "visual_mode": effective_visual_mode,
                    "attempts": {
                        "stage1": stage1_attempts,
                        "stage2": stage2_attempts,
                    },
                    "vision_facts": vision_facts,
                    "usage": merged_usage,
                    "raw": {
                        "stage1": stage1_result.get("raw", {}),
                        "stage2": stage2_result.get("raw", {}),
                    },
                }
                return (
                    merged_result.get("text", ""),
                    dumps(merged_result),
                    dumps(merged_usage),
                    merged_result.get("reasoning", ""),
                )

            result, attempts = _call_with_retry(
                adapter,
                parsed,
                api_key,
                系统提示词,
                用户提示词,
                温度,
                最大Token数,
                随机种子,
                response_format,
                ref_image=参考图片,
            )
            result["channel"] = adapter_protocol
            result["channel_label"] = _channel_label(adapter_protocol, 参考图片 is not None, effective_visual_mode)
            result["visual_mode"] = effective_visual_mode
            result["attempts"] = attempts
            return (
                result.get("text", ""),
                dumps(result),
                dumps(result.get("usage", {})),
                result.get("reasoning", ""),
            )
        except Exception as exc:
            error = error_payload("text_api_error", str(exc), parsed)
            if adapter_protocol:
                error["channel"] = adapter_protocol
                error["channel_label"] = _channel_label(adapter_protocol, 参考图片 is not None, effective_visual_mode)
            error["visual_mode"] = effective_visual_mode
            return ("", dumps(error), "{}", "")
