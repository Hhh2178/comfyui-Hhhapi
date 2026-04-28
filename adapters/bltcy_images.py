import time
from io import BytesIO

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .base import BaseAdapter
from ..utils.image import concat_grid, decode_image_item, pil_to_png_bytes, tensor_to_pil_list


class BltcyImagesAdapter(BaseAdapter):
    protocol = "bltcy_images"

    _session = None
    _TASK_PENDING = {"pending", "queued", "running", "processing", "in_progress", "submitted"}
    _TASK_SUCCESS = {"success", "succeeded", "completed", "done", "finished"}
    _TASK_FAILED = {"failed", "failure", "error", "cancelled", "canceled", "timeout"}

    @classmethod
    def _http_session(cls):
        if cls._session is None:
            session = requests.Session()
            retry = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET", "POST"],
            )
            adapter = HTTPAdapter(max_retries=retry)
            session.mount("https://", adapter)
            session.mount("http://", adapter)
            cls._session = session
        return cls._session

    def call_gpt_image(
        self,
        config,
        api_key,
        prompt,
        size,
        n=1,
        quality="medium",
        seed=-1,
        output_format="png",
        input_fidelity="high",
        response_format="url",
        images=None,
        mask=None,
    ):
        started_at = time.perf_counter()
        images = images or []
        if images:
            result = self._call_gpt_edit(
                config=config,
                api_key=api_key,
                prompt=prompt,
                size=size,
                n=n,
                quality=quality,
                seed=seed,
                output_format=output_format,
                input_fidelity=input_fidelity,
                response_format=response_format,
                images=images,
                mask=mask,
            )
        else:
            result = self._call_gpt_generate(
                config=config,
                api_key=api_key,
                prompt=prompt,
                size=size,
                n=n,
                quality=quality,
                seed=seed,
                output_format=output_format,
                response_format=response_format,
            )
        result.setdefault("timings", {})
        result["timings"]["total_seconds"] = round(time.perf_counter() - started_at, 4)
        return result

    def call_nano_image(self, config, api_key, prompt, aspect_ratio, image_size, n=1, images=None, mask=None):
        images = images or []
        if images:
            return self._call_nano_edit(config, api_key, prompt, aspect_ratio, image_size, n, images, mask)
        return self._call_nano_generate(config, api_key, prompt, aspect_ratio, image_size, n)

    def call_nano_image_async_tasks(
        self,
        config,
        api_key,
        prompt,
        aspect_ratio,
        image_size,
        task_count=1,
        poll_interval=3,
        images=None,
        mask=None,
    ):
        started_at = time.perf_counter()
        images = images or []
        total_tasks = max(1, int(task_count or 1))
        submit_timings = []
        task_ids = []

        for _ in range(total_tasks):
            submit_started = time.perf_counter()
            if images:
                task_id = self._submit_nano_edit_async(config, api_key, prompt, aspect_ratio, image_size, images, mask)
            else:
                task_id = self._submit_nano_generate_async(config, api_key, prompt, aspect_ratio, image_size)
            submit_timings.append(round(time.perf_counter() - submit_started, 4))
            task_ids.append(task_id)

        poll_started = time.perf_counter()
        aggregated_images = []
        aggregated_urls = []
        task_results = []
        download_entries = []
        timeout_seconds = max(int(config.get("timeout", 120)), int(poll_interval or 3))
        deadline = time.time() + max(timeout_seconds, timeout_seconds * total_tasks)

        for task_id in task_ids:
            payload = self._poll_image_task_result(config, api_key, task_id, poll_interval, deadline)
            normalized = self._normalize_image_response(config, payload)
            if normalized.get("images"):
                aggregated_images.extend(normalized.get("images", []))
            if normalized.get("image_urls"):
                aggregated_urls.extend(normalized.get("image_urls", []))
            task_results.append({
                "task_id": task_id,
                "status": self._extract_task_status(payload),
                "image_count": normalized.get("image_count", 0),
                "raw": payload,
            })
            download_entries.extend(normalized.get("timings", {}).get("downloaded_items", []))

        return {
            "ok": True,
            "provider_id": config.get("provider_id", ""),
            "family": config.get("family", ""),
            "model": config.get("model", ""),
            "image_count": len(aggregated_images),
            "images": aggregated_images,
            "image_urls": aggregated_urls,
            "raw": {"tasks": task_results},
            "task_ids": task_ids,
            "timings": {
                "submit_count": total_tasks,
                "submit_seconds_each": submit_timings,
                "submit_seconds_total": round(sum(submit_timings), 4),
                "poll_seconds_total": round(time.perf_counter() - poll_started, 4),
                "downloaded_items": download_entries,
                "download_seconds_total": round(sum(entry.get("download_seconds", 0.0) for entry in download_entries), 4),
                "decode_seconds_total": round(sum(entry.get("decode_seconds", 0.0) for entry in download_entries), 4),
                "download_total_seconds": round(sum(entry.get("total_seconds", 0.0) for entry in download_entries), 4),
                "downloaded_count": len(download_entries),
                "total_seconds": round(time.perf_counter() - started_at, 4),
            },
        }

    def _call_gpt_generate(self, config, api_key, prompt, size, n, quality, seed, output_format, response_format):
        started_at = time.perf_counter()
        url = f"{config.get('base_url', '').rstrip('/')}{config.get('paths', {}).get('generate', '/images/generations')}"
        payload = {
            "model": config.get("model", ""),
            "prompt": prompt,
            "n": int(max(1, int(n or 1))),
            "quality": quality or "medium",
            "size": size,
            "output_format": output_format or "png",
            "response_format": response_format or "url",
        }
        if int(seed) >= 0:
            payload["seed"] = int(seed)

        before_request = time.perf_counter()
        resp = self._http_session().post(
            url,
            headers=self.build_headers(config, api_key),
            json=payload,
            timeout=int(config.get("timeout", 120)),
        )
        after_response = time.perf_counter()
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")
        payload_json = resp.json()
        after_json = time.perf_counter()
        result = self._normalize_image_response(config, payload_json)
        result.setdefault("timings", {})
        result["timings"].update({
            "request_mode": "text_to_image",
            "preprocess_seconds": round(before_request - started_at, 4),
            "request_seconds": round(after_response - before_request, 4),
            "json_parse_seconds": round(after_json - after_response, 4),
        })
        return result

    def _call_gpt_edit(self, config, api_key, prompt, size, n, quality, seed, output_format, input_fidelity, response_format, images, mask):
        started_at = time.perf_counter()
        url = f"{config.get('base_url', '').rstrip('/')}{config.get('paths', {}).get('edit', '/images/edits')}"
        merge_started = time.perf_counter()
        merged_image = self._merge_reference_images(images)
        merge_finished = time.perf_counter()
        files = [
            ("prompt", (None, prompt)),
            ("model", (None, config.get("model", ""))),
            ("n", (None, str(int(max(1, int(n or 1)))))),
            ("input_fidelity", (None, input_fidelity or "high")),
            ("quality", (None, quality or "medium")),
            ("size", (None, size)),
            ("output_format", (None, output_format or "png")),
            ("response_format", (None, response_format or "url")),
            ("image", ("image.png", BytesIO(pil_to_png_bytes(merged_image)), "image/png")),
        ]
        if int(seed) >= 0:
            files.append(("seed", (None, str(int(seed)))))
        if mask is not None:
            mask_pil = tensor_to_pil_list(mask)[0]
            files.append(("mask", ("mask.png", BytesIO(pil_to_png_bytes(mask_pil)), "image/png")))

        before_request = time.perf_counter()
        resp = self._http_session().post(
            url,
            headers=self.build_headers(config, api_key, content_type=None),
            files=files,
            timeout=int(config.get("timeout", 120)),
        )
        after_response = time.perf_counter()
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")
        payload_json = resp.json()
        after_json = time.perf_counter()
        result = self._normalize_image_response(config, payload_json)
        result.setdefault("timings", {})
        result["timings"].update({
            "request_mode": "image_to_image",
            "reference_merge_seconds": round(merge_finished - merge_started, 4),
            "preprocess_seconds": round(before_request - started_at, 4),
            "request_seconds": round(after_response - before_request, 4),
            "json_parse_seconds": round(after_json - after_response, 4),
        })
        return result

    def _call_nano_generate(self, config, api_key, prompt, aspect_ratio, image_size, n):
        url = f"{config.get('base_url', '').rstrip('/')}{config.get('paths', {}).get('generate', '/images/generations')}"
        payload = {
            "model": config.get("model", ""),
            "prompt": prompt,
            "n": int(max(1, int(n or 1))),
        }
        if aspect_ratio and aspect_ratio != "auto":
            payload["aspect_ratio"] = aspect_ratio
        if image_size and image_size != "auto":
            payload["image_size"] = image_size
        result = self.post_json(url, self.build_headers(config, api_key), payload, int(config.get("timeout", 120)))
        return self._normalize_image_response(config, result)

    def _call_nano_edit(self, config, api_key, prompt, aspect_ratio, image_size, n, images, mask):
        url = f"{config.get('base_url', '').rstrip('/')}{config.get('paths', {}).get('edit', '/images/edits')}"
        data = {
            "model": config.get("model", ""),
            "prompt": prompt,
            "n": str(int(max(1, int(n or 1)))),
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
        resp = self._http_session().post(
            url,
            headers=self.build_headers(config, api_key, content_type=None),
            data=data,
            files=files,
            timeout=int(config.get("timeout", 120)),
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")
        return self._normalize_image_response(config, resp.json())

    def _submit_nano_generate_async(self, config, api_key, prompt, aspect_ratio, image_size):
        url = f"{config.get('base_url', '').rstrip('/')}{config.get('paths', {}).get('generate', '/images/generations')}"
        payload = {
            "model": config.get("model", ""),
            "prompt": prompt,
            "n": 1,
        }
        if aspect_ratio and aspect_ratio != "auto":
            payload["aspect_ratio"] = aspect_ratio
        if image_size and image_size != "auto":
            payload["image_size"] = image_size
        resp = self._http_session().post(
            url,
            headers=self.build_headers(config, api_key),
            params={"async": "true"},
            json=payload,
            timeout=int(config.get("timeout", 120)),
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")
        return self._extract_task_id(resp.json())

    def _submit_nano_edit_async(self, config, api_key, prompt, aspect_ratio, image_size, images, mask):
        url = f"{config.get('base_url', '').rstrip('/')}{config.get('paths', {}).get('edit', '/images/edits')}"
        data = {
            "model": config.get("model", ""),
            "prompt": prompt,
            "n": "1",
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
        resp = self._http_session().post(
            url,
            headers=self.build_headers(config, api_key, content_type=None),
            params={"async": "true"},
            data=data,
            files=files,
            timeout=int(config.get("timeout", 120)),
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")
        return self._extract_task_id(resp.json())

    def _poll_image_task_result(self, config, api_key, task_id, poll_interval, deadline):
        while time.time() < deadline:
            payload = self._fetch_task_payload(config, api_key, task_id)
            status = self._extract_task_status(payload)
            if status in self._TASK_SUCCESS and self._task_has_images(payload):
                return payload
            if status in self._TASK_FAILED:
                raise RuntimeError(self._extract_task_error(payload) or f"异步任务失败: {status}")
            time.sleep(max(1, int(poll_interval or 3)))
        raise RuntimeError(f"异步任务轮询超时: {task_id}")

    def _fetch_task_payload(self, config, api_key, task_id):
        url = f"{config.get('base_url', '').rstrip('/')}/images/tasks/{task_id}"
        resp = self._http_session().get(
            url,
            headers=self.build_headers(config, api_key),
            timeout=(10, 30),
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")
        return resp.json()

    def _extract_task_id(self, payload):
        for item in self._collect_dicts(payload):
            task_id = item.get("task_id") or item.get("taskId") or item.get("id")
            if task_id:
                return str(task_id)
        raise RuntimeError(f"异步提交未返回 task_id: {payload}")

    def _extract_task_status(self, payload):
        for item in self._collect_dicts(payload):
            status = item.get("status") or item.get("task_status") or item.get("state")
            if status:
                return str(status).strip().lower()
        return ""

    def _extract_task_error(self, payload):
        for item in self._collect_dicts(payload):
            for key in ("fail_reason", "failReason", "message", "error", "description"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return ""

    def _task_has_images(self, payload):
        return bool(self._collect_image_items(payload))

    def _collect_dicts(self, value):
        items = []
        if isinstance(value, dict):
            items.append(value)
            for nested in value.values():
                items.extend(self._collect_dicts(nested))
        elif isinstance(value, list):
            for nested in value:
                items.extend(self._collect_dicts(nested))
        return items

    def _merge_reference_images(self, images):
        pil_images = []
        for image in images:
            pil_images.extend(tensor_to_pil_list(image))
        if not pil_images:
            raise ValueError("at least one image is required")
        if len(pil_images) == 1:
            return pil_images[0]
        return concat_grid(pil_images)

    def _build_image_files(self, images):
        files = []
        for image_index, image in enumerate(images, start=1):
            for batch_index, pil_image in enumerate(tensor_to_pil_list(image), start=1):
                filename = f"image_{image_index}_{batch_index}.png"
                files.append(("image", (filename, BytesIO(pil_to_png_bytes(pil_image)), "image/png")))
        if not files:
            raise ValueError("at least one image is required")
        return files

    def _collect_image_items(self, result):
        items = []
        if isinstance(result, dict):
            data = result.get("data")
            if isinstance(data, list):
                items.extend(item for item in data if isinstance(item, dict))
            elif isinstance(data, dict):
                items.extend(self._collect_image_items(data))
            for key in ("url", "image_url", "download_url"):
                value = result.get(key)
                if isinstance(value, str) and value.strip():
                    items.append({"url": value.strip()})
            outputs = result.get("outputs")
            if isinstance(outputs, list):
                for output in outputs:
                    if isinstance(output, str):
                        items.append({"url": output})
                    elif isinstance(output, dict):
                        items.append(output)
        elif isinstance(result, list):
            for item in result:
                items.extend(self._collect_image_items(item))
        return items

    def _normalize_image_response(self, config, result):
        images = []
        urls = []
        download_entries = []
        for item in self._collect_image_items(result):
            if not isinstance(item, dict):
                continue
            pil, url, timing = decode_image_item(item)
            if pil is not None:
                images.append(pil)
            if url:
                urls.append(url)
            if timing:
                download_entries.append({
                    "url": timing.get("url", ""),
                    "source": timing.get("source", ""),
                    "download_seconds": timing.get("download_seconds", 0.0),
                    "decode_seconds": timing.get("decode_seconds", 0.0),
                    "total_seconds": timing.get("total_seconds", 0.0),
                })
        return {
            "ok": True,
            "provider_id": config.get("provider_id", ""),
            "family": config.get("family", ""),
            "model": config.get("model", ""),
            "image_count": len(images),
            "images": images,
            "image_urls": urls,
            "raw": result,
            "timings": {
                "downloaded_items": download_entries,
                "download_seconds_total": round(sum(entry.get("download_seconds", 0.0) for entry in download_entries), 4),
                "decode_seconds_total": round(sum(entry.get("decode_seconds", 0.0) for entry in download_entries), 4),
                "download_total_seconds": round(sum(entry.get("total_seconds", 0.0) for entry in download_entries), 4),
                "downloaded_count": len(download_entries),
            },
        }
