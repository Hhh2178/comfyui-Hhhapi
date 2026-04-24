import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .base import BaseAdapter
from ..utils.image import tensor_to_pil_list


def _extract_text(payload):
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("text", "description", "content", "result", "answer", "output"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
            if isinstance(value, dict):
                nested = _extract_text(value)
                if nested:
                    return nested
        data = payload.get("data")
        if isinstance(data, dict):
            nested = _extract_text(data)
            if nested:
                return nested
    return ""


class MiniMaxVisionAdapter(BaseAdapter):
    protocol = "minimax_cli_vision"

    def _runner(self):
        for cmd in ("mmx", "mmx.cmd", "mmx.exe"):
            found = shutil.which(cmd)
            if found:
                return [found]

        explicit_mmx = os.environ.get("HHHAPI_MMX")
        if explicit_mmx and Path(explicit_mmx).exists():
            return [explicit_mmx]

        explicit_npx = os.environ.get("HHHAPI_NPX")
        if explicit_npx and Path(explicit_npx).exists():
            return [explicit_npx, "-y", "mmx-cli"]

        npx_candidates = [
            shutil.which("npx"),
            shutil.which("npx.cmd"),
            r"D:\ClaudeCode\NodeJS\npx.cmd",
            r"C:\Program Files\nodejs\npx.cmd",
            r"C:\Program Files (x86)\nodejs\npx.cmd",
        ]
        for candidate in npx_candidates:
            if candidate and Path(candidate).exists():
                return [str(candidate), "-y", "mmx-cli"]

        raise RuntimeError(
            "未找到 MiniMax CLI。当前服务端进程无法定位 mmx/npx，可设置 HHHAPI_NPX 或安装 mmx-cli。"
        )

    def _run(self, command, env, timeout):
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=timeout,
        )
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "MiniMax CLI 调用失败").strip()[:1000])
        return (proc.stdout or "").strip()

    def call_text(self, config, api_key, system_prompt, prompt, temperature, max_tokens, seed, response_format, ref_image=None):
        if ref_image is None:
            raise RuntimeError("MiniMax 图片理解协议需要参考图片输入。")

        images = tensor_to_pil_list(ref_image)
        if not images:
            raise RuntimeError("参考图片为空。")

        runner = self._runner()
        timeout = int(config.get("timeout", 120))
        region = "cn" if "minimaxi.com" in str(config.get("base_url", "")).lower() else ""

        with tempfile.TemporaryDirectory(prefix="hhhapi_minimax_") as temp_dir:
            image_path = os.path.join(temp_dir, "input.png")
            images[0].save(image_path, format="PNG")

            user_prompt = (prompt or "").strip() or "请分析这张图片。"
            command = [
                *runner,
                "--api-key", api_key,
                "--non-interactive",
                "--output", "json",
            ]
            if region:
                command.extend(["--region", region])
            command.extend([
                "vision",
                "describe",
                "--image", image_path,
                "--prompt", user_prompt,
            ])
            cli_output = self._run(
                command,
                os.environ.copy(),
                timeout,
            )

            try:
                raw = json.loads(cli_output)
            except Exception:
                raw = {"raw_text": cli_output}

            text = _extract_text(raw) or cli_output
            return {
                "ok": True,
                "task_type": "text",
                "provider_id": config.get("provider_id", ""),
                "model": config.get("model", ""),
                "text": text,
                "reasoning": "",
                "usage": raw.get("usage", {}) if isinstance(raw, dict) else {},
                "raw": raw,
            }
