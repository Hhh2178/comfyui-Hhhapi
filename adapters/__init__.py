from .openai_chat import OpenAIChatAdapter
from .openai_images import OpenAIImagesAdapter
from .minimax_vision import MiniMaxVisionAdapter


ADAPTERS = {
    OpenAIChatAdapter.protocol: OpenAIChatAdapter(),
    OpenAIImagesAdapter.protocol: OpenAIImagesAdapter(),
    MiniMaxVisionAdapter.protocol: MiniMaxVisionAdapter(),
}


def get_adapter(protocol):
    adapter = ADAPTERS.get(protocol)
    if not adapter:
        raise ValueError(f"unsupported protocol: {protocol}")
    return adapter
