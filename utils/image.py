import base64
from io import BytesIO

import numpy as np
import torch
from PIL import Image


def tensor_to_pil_list(image):
    if image is None:
        return []
    batch_count = image.size(0) if len(image.shape) > 3 else 1
    if batch_count > 1:
        out = []
        for i in range(batch_count):
            out.extend(tensor_to_pil_list(image[i]))
        return out
    arr = np.clip(255.0 * image.cpu().numpy().squeeze(), 0, 255).astype(np.uint8)
    if arr.ndim == 2:
        return [Image.fromarray(arr, mode="L")]
    if arr.shape[-1] == 4:
        return [Image.fromarray(arr, mode="RGBA")]
    return [Image.fromarray(arr[..., :3], mode="RGB")]


def pil_to_tensor(image):
    if image.mode != "RGB":
        image = image.convert("RGB")
    arr = np.array(image).astype(np.float32) / 255.0
    return torch.from_numpy(arr)[None,]


def pil_list_to_batch(images):
    if not images:
        return torch.empty(0)
    return torch.cat([pil_to_tensor(img) for img in images], dim=0)


def pil_to_png_bytes(image):
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def image_tensor_to_data_url(image):
    pil = tensor_to_pil_list(image)[0]
    data = base64.b64encode(pil_to_png_bytes(pil)).decode("utf-8")
    return f"data:image/png;base64,{data}"


def decode_image_item(item):
    if item.get("b64_json"):
        raw = base64.b64decode(item["b64_json"])
        return Image.open(BytesIO(raw)).convert("RGB"), ""
    url = item.get("url") or item.get("image_url") or item.get("download_url")
    if url:
        import requests
        resp = requests.get(url, timeout=90)
        resp.raise_for_status()
        return Image.open(BytesIO(resp.content)).convert("RGB"), url
    return None, ""


def concat_grid(images):
    if len(images) <= 1:
        return images[0]
    max_height = max(img.height for img in images)
    total_width = sum(img.width for img in images)
    canvas = Image.new("RGB", (total_width, max_height), "white")
    x = 0
    for img in images:
        canvas.paste(img.convert("RGB"), (x, 0))
        x += img.width
    return canvas

