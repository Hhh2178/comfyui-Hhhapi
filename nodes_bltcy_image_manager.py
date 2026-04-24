from . import image_provider_store
from .utils.response import dumps


class HhhapiBltcyImageManager:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "操作": (["打开管理面板提示", "导出图片配置"], {"default": "打开管理面板提示"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("结果JSON",)
    FUNCTION = "manage"
    CATEGORY = "Hhh/柏拉图图片API"

    def manage(self, 操作="打开管理面板提示", **kwargs):
        if 操作 == "打开管理面板提示":
            return (dumps({
                "ok": True,
                "message": "请在画布右键菜单或节点按钮中打开「Hhh 柏拉图图片API管理」面板。",
            }),)
        return (dumps({"ok": True, "config": image_provider_store.load_config()}),)
