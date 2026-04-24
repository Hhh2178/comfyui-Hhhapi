from io import BytesIO

import requests

from .base import BaseAdapter
from ..utils.image import concat_grid, decode_image_item, pil_to_png_bytes, tensor_to_pil_list


class OpenAIImagesAdapter(BaseAdapter):
    protocol = "openai_images"

    def call_text_to_image(self, config, api_key, prompt, negative_prompt, size, aspect_ratio, quality, n, seed, output_format):
        base_url = config.get("base_url", "").rstrip("/")
        path = config.get("paths", {}).get("generate", "/images/generations")
        url = f"{base_url}{path}"
        full_prompt = prompt if not negative_prompt else f"{prompt}\nNegative prompt: {negative_prompt}"
        payload = {
            "model": config.get("model", ""),
            "prompt": full_prompt,
            "n": int(n),
            "response_format": "b64_json",
        }
        if size and size != "auto":
            payload["size"] = size
        if quality and quality != "auto":
            payload["quality"] = quality
        if aspect_ratio and aspect_ratio != "auto":
            payload["aspect_ratio"] = aspect_ratio
        if int(seed) >= 0:
            payload["seed"] = int(seed)
        if output_format:
            payload["output_format"] = output_format

        result = self.post_json(
            url,
            self.build_headers(config, api_key),
            payload,
            int(config.get("timeout", 120)),
        )
        return self._normalize_image_response(config, result)

    def call_image_to_image(self, config, api_key, prompt, images, mask, size, quality, n, seed, output_format, multi_image_mode):
        base_url = config.get("base_url", "").rstrip("/")
        path = config.get("paths", {}).get("edit", "/images/edits")
        url = f"{base_url}{path}"
        pil_images = []
        for image in images:
            pil_images.extend(tensor_to_pil_list(image))
        if not pil_images:
            raise ValueError("at least one image is required")

        data = {
            "model": config.get("model", ""),
            "prompt": prompt,
            "n": str(int(n)),
        }
        if size and size != "auto":
            data["size"] = size
        if quality and quality != "auto":
            data["quality"] = quality
        if int(seed) >= 0:
            data["seed"] = str(int(seed))
        if output_format:
            data["output_format"] = output_format

        files = []
        if multi_image_mode == "concat_grid":
            merged = concat_grid(pil_images)
            files.append(("image", ("image.png", BytesIO(pil_to_png_bytes(merged)), "image/png")))
        else:
            for idx, pil in enumerate(pil_images):
                files.append(("image", (f"image_{idx + 1}.png", BytesIO(pil_to_png_bytes(pil)), "image/png")))

        if mask is not None:
            mask_pil = tensor_to_pil_list(mask)[0]
            files.append(("mask", ("mask.png", BytesIO(pil_to_png_bytes(mask_pil)), "image/png")))

        headers = self.build_headers(config, api_key, content_type=None)
        resp = requests.post(url, headers=headers, data=data, files=files, timeout=int(config.get("timeout", 120)))
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")
        return self._normalize_image_response(config, resp.json())

    def _normalize_image_response(self, config, result):
        images = []
        urls = []
        for item in result.get("data", []):
            if not isinstance(item, dict):
                continue
            pil, url = decode_image_item(item)
            if pil is not None:
                images.append(pil)
            if url:
                urls.append(url)
        return {
            "ok": True,
            "task_type": config.get("task_type", ""),
            "provider_id": config.get("provider_id", ""),
            "model": config.get("model", ""),
            "images": images,
            "image_urls": urls,
            "raw": result,
        }

