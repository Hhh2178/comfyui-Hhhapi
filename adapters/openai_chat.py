import re

from .base import BaseAdapter
from ..utils.image import image_tensor_to_data_url


def _extract_content(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content") or ""
                if text:
                    parts.append(str(text))
        return "".join(parts)
    return ""


def _extract_reasoning_details(message):
    details = []
    reasoning_details = []
    if isinstance(message, dict):
        reasoning_details = message.get("reasoning_details") or []
    if isinstance(reasoning_details, list):
        for item in reasoning_details:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content") or ""
                if text:
                    details.append(str(text))
            elif isinstance(item, str):
                details.append(item)
    return "".join(details)


def _split_thinking(text):
    if not text:
        return "", ""
    matches = re.findall(r"<think>(.*?)</think>", text, flags=re.DOTALL | re.IGNORECASE)
    if not matches:
        return "", text
    reasoning = "\n".join(part.strip() for part in matches if part and part.strip())
    clean_text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    return reasoning, clean_text


def _should_enable_reasoning_split(config):
    provider_id = str(config.get("provider_id", "")).lower()
    model = str(config.get("model", ""))
    return "minimax" in provider_id or model.startswith("MiniMax-")


class OpenAIChatAdapter(BaseAdapter):
    protocol = "openai_chat_completions"

    def call_text(self, config, api_key, system_prompt, prompt, temperature, max_tokens, seed, response_format, ref_image=None):
        base_url = config.get("base_url", "").rstrip("/")
        path = config.get("paths", {}).get("chat", "/chat/completions")
        url = f"{base_url}{path}"
        user_content = prompt
        if ref_image is not None:
            user_content = [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_tensor_to_data_url(ref_image)}},
            ]
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_content})
        payload = {
            "model": config.get("model", ""),
            "messages": messages,
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
        }
        if _should_enable_reasoning_split(config):
            payload["reasoning_split"] = True
        if int(seed) >= 0:
            payload["seed"] = int(seed)
        if response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}

        result = self.post_json(
            url,
            self.build_headers(config, api_key),
            payload,
            int(config.get("timeout", 120)),
        )
        if isinstance(result, dict) and result.get("error"):
            raise RuntimeError(f"API error: {result.get('error')}")
        if not isinstance(result, dict):
            raise RuntimeError(f"API returned non-object response: {type(result).__name__}")
        text = ""
        choices = result.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError(
                "API returned no choices. "
                f"provider={config.get('provider_id', '')}, model={config.get('model', '')}, raw={result}"
            )
        first = choices[0] or {}
        message = first.get("message") or first.get("delta") or {}
        text = _extract_content(message.get("content")) or _extract_content(first.get("text"))
        reasoning = _extract_reasoning_details(message)
        inline_reasoning, clean_text = _split_thinking(text)
        reasoning = reasoning or inline_reasoning
        text = clean_text if inline_reasoning else text
        if not text:
            raise RuntimeError(
                "API returned choices but no text content. "
                f"provider={config.get('provider_id', '')}, model={config.get('model', '')}, raw={result}"
            )
        return {
            "ok": True,
            "task_type": "text",
            "provider_id": config.get("provider_id", ""),
            "model": config.get("model", ""),
            "text": text,
            "reasoning": reasoning,
            "usage": result.get("usage", {}),
            "raw": result,
        }
