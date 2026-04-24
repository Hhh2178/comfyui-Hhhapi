from io import BytesIO

import requests

from .base import BaseAdapter
from ..utils.image import decode_image_item, pil_to_png_bytes, tensor_to_pil_list


class BltcyImagesAdapter(BaseAdapter):
    protocol = "bltcy_images"

    def call_gpt_image(
        self,
        config,
        api_key,
        prompt,
        size,
        aspect_ratio,
        n=1,
        quality="auto",
        seed=-1,
        output_format="png",
        input_fidelity="high",
        images=None,
        mask=None,
    ):
        images = images or []
        if images:
            return self._call_gpt_with_fallback(
                self._call_gpt_edit,
                int(n),
                int(seed),
                config,
                api_key,
                prompt,
                size,
                quality,
                seed,
                output_format,
                input_fidelity,
                images,
                mask,
            )
        return self._call_gpt_with_fallback(
            self._call_gpt_generate,
            int(n),
            int(seed),
            config,
            api_key,
            prompt,
            size,
            aspect_ratio,
            quality,
            seed,
            output_format,
        )

    def _call_gpt_with_fallback(self, func, requested_n, base_seed, config, api_key, prompt, size, *args):
        result = func(config, api_key, prompt, size, requested_n, *args)
        if requested_n <= 1 or result.get("image_count", 0) >= requested_n:
            return result

        merged = {
            "ok": True,
            "provider_id": result.get("provider_id", ""),
            "family": result.get("family", ""),
            "model": result.get("model", ""),
            "images": list(result.get("images", [])),
            "image_urls": list(result.get("image_urls", [])),
            "raw": [result.get("raw", {})],
        }
        remaining = requested_n - len(merged["images"])

        while remaining > 0:
            single_requested_n = 1
            single_args = list(args)
            if int(base_seed) >= 0:
                generated_count = len(merged["images"])
                if func == self._call_gpt_generate:
                    single_args[2] = int(base_seed) + generated_count
                else:
                    single_args[1] = int(base_seed) + generated_count
            extra = func(config, api_key, prompt, size, single_requested_n, *single_args)
            merged["images"].extend(extra.get("images", []))
            merged["image_urls"].extend(extra.get("image_urls", []))
            merged["raw"].append(extra.get("raw", {}))
            remaining = requested_n - len(merged["images"])
            if extra.get("image_count", 0) <= 0:
                break

        merged["images"] = merged["images"][:requested_n]
        merged["image_urls"] = merged["image_urls"][:requested_n]
        merged["image_count"] = len(merged["images"])
        return merged

    def call_nano_image(self, config, api_key, prompt, aspect_ratio, image_size, images=None, mask=None):
        images = images or []
        if images:
            return self._call_nano_edit(config, api_key, prompt, aspect_ratio, image_size, images, mask)
        return self._call_nano_generate(config, api_key, prompt, aspect_ratio, image_size)

    def _call_gpt_generate(self, config, api_key, prompt, size, n, aspect_ratio, quality, seed, output_format):
        url = f"{config.get('base_url', '').rstrip('/')}{config.get('paths', {}).get('generate', '/images/generations')}"
        payload = {
            "model": config.get("model", ""),
            "prompt": prompt,
            "n": int(n),
        }
        if size and size != "auto":
            payload["size"] = size
        if aspect_ratio and aspect_ratio != "auto":
            payload["aspect_ratio"] = aspect_ratio
        if quality and quality != "auto":
            payload["quality"] = quality
        if int(seed) >= 0:
            payload["seed"] = int(seed)
        if output_format:
            payload["output_format"] = output_format
        result = self.post_json(url, self.build_headers(config, api_key), payload, int(config.get("timeout", 120)))
        return self._normalize_image_response(config, result)

    def _call_gpt_edit(self, config, api_key, prompt, size, n, quality, seed, output_format, input_fidelity, images, mask):
        url = f"{config.get('base_url', '').rstrip('/')}{config.get('paths', {}).get('edit', '/images/edits')}"
        data = {
            "model": config.get("model", ""),
            "prompt": prompt,
            "n": str(int(n)),
        }
        if size and size != "auto":
            data["size"] = size
        if quality and quality != "auto":
            data["quality"] = quality
        if output_format:
            data["output_format"] = output_format
        if input_fidelity:
            data["input_fidelity"] = input_fidelity
        if int(seed) >= 0:
            data["seed"] = str(int(seed))
        files = self._build_image_files(images)
        if mask is not None:
            mask_pil = tensor_to_pil_list(mask)[0]
            files.append(("mask", ("mask.png", BytesIO(pil_to_png_bytes(mask_pil)), "image/png")))
        resp = requests.post(
            url,
            headers=self.build_headers(config, api_key, content_type=None),
            data=data,
            files=files,
            timeout=int(config.get("timeout", 120)),
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")
        return self._normalize_image_response(config, resp.json())

    def _call_nano_generate(self, config, api_key, prompt, aspect_ratio, image_size):
        url = f"{config.get('base_url', '').rstrip('/')}{config.get('paths', {}).get('generate', '/images/generations')}"
        payload = {
            "model": config.get("model", ""),
            "prompt": prompt,
        }
        if aspect_ratio and aspect_ratio != "auto":
            payload["aspect_ratio"] = aspect_ratio
        if image_size and image_size != "auto":
            payload["image_size"] = image_size
        result = self.post_json(url, self.build_headers(config, api_key), payload, int(config.get("timeout", 120)))
        return self._normalize_image_response(config, result)

    def _call_nano_edit(self, config, api_key, prompt, aspect_ratio, image_size, images, mask):
        url = f"{config.get('base_url', '').rstrip('/')}{config.get('paths', {}).get('edit', '/images/edits')}"
        data = {
            "model": config.get("model", ""),
            "prompt": prompt,
            "response_format": "url",
        }
        if aspect_ratio and aspect_ratio != "auto":
            data["aspect_ratio"] = aspect_ratio
        if image_size and image_size != "auto":
            data["image_size"] = image_size
        files = self._build_image_files(images)
        if mask is not None:
            mask_pil = tensor_to_pil_list(mask)[0]
            files.append(("mask", ("mask.png", BytesIO(pil_to_png_bytes(mask_pil)), "image/png")))
        resp = requests.post(
            url,
            headers=self.build_headers(config, api_key, content_type=None),
            data=data,
            files=files,
            timeout=int(config.get("timeout", 120)),
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")
        return self._normalize_image_response(config, resp.json())

    def _build_image_files(self, images):
        files = []
        for image_index, image in enumerate(images, start=1):
            for batch_index, pil_image in enumerate(tensor_to_pil_list(image), start=1):
                filename = f"image_{image_index}_{batch_index}.png"
                files.append(("image", (filename, BytesIO(pil_to_png_bytes(pil_image)), "image/png")))
        if not files:
            raise ValueError("at least one image is required")
        return files

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
            "provider_id": config.get("provider_id", ""),
            "family": config.get("family", ""),
            "model": config.get("model", ""),
            "image_count": len(images),
            "images": images,
            "image_urls": urls,
            "raw": result,
        }
