import pytest
from llama_index.llms.bedrock_converse.utils import (
    get_model_name,
    tools_to_converse_tools,
)
from io import BytesIO
from unittest.mock import MagicMock, patch

from llama_index.core.base.llms.types import (
    AudioBlock,
    ImageBlock,
    MessageRole,
    TextBlock,
    CacheControl,
    CachePoint,
)
from llama_index.core.tools import FunctionTool
from llama_index.llms.bedrock_converse.utils import (
    __get_img_format_from_image_mimetype,
    _content_block_to_bedrock_format,
)


def test_get_model_name_translates_us():
    assert (
        get_model_name("us.meta.llama3-2-3b-instruct-v1:0")
        == "meta.llama3-2-3b-instruct-v1:0"
    )


def test_get_model_name_does_nottranslate_cn():
    assert (
        get_model_name("cn.meta.llama3-2-3b-instruct-v1:0")
        == "cn.meta.llama3-2-3b-instruct-v1:0"
    )


def test_get_model_name_does_nottranslate_unsupported():
    assert get_model_name("cohere.command-r-plus-v1:0") == "cohere.command-r-plus-v1:0"


def test_get_model_name_throws_inference_profile_exception():
    with pytest.raises(ValueError):
        assert get_model_name("us.cohere.command-r-plus-v1:0")


def test_get_img_format_jpeg():
    assert __get_img_format_from_image_mimetype("image/jpeg") == "jpeg"


def test_get_img_format_png():
    assert __get_img_format_from_image_mimetype("image/png") == "png"


def test_get_img_format_gif():
    assert __get_img_format_from_image_mimetype("image/gif") == "gif"


def test_get_img_format_webp():
    assert __get_img_format_from_image_mimetype("image/webp") == "webp"


def test_get_img_format_unsupported(caplog):
    result = __get_img_format_from_image_mimetype("image/unsupported")
    assert result == "png"
    assert "Unsupported image mimetype" in caplog.text


def test_content_block_to_bedrock_format_text():
    text_block = TextBlock(text="Hello, world!")
    result = _content_block_to_bedrock_format(text_block, MessageRole.USER)
    assert result == {"text": "Hello, world!"}


def test_cache_point_block():
    cache_point = CachePoint(cache_control=CacheControl(type="default"))
    result = _content_block_to_bedrock_format(cache_point, MessageRole.USER)
    assert result == {"cachePoint": {"type": "default"}}
    cache_point1 = CachePoint(cache_control=CacheControl(type="persistent"))
    result1 = _content_block_to_bedrock_format(cache_point1, MessageRole.USER)
    assert result1 == {"cachePoint": {"type": "default"}}


@patch("llama_index.core.base.llms.types.ImageBlock.resolve_image")
def test_content_block_to_bedrock_format_image_user(mock_resolve):
    mock_bytes = BytesIO(b"fake_image_data")
    mock_bytes.read = MagicMock(return_value=b"fake_image_data")
    mock_resolve.return_value = mock_bytes

    image_block = ImageBlock(image=b"", image_mimetype="image/png")

    result = _content_block_to_bedrock_format(image_block, MessageRole.USER)

    assert "image" in result
    assert result["image"]["format"] == "png"
    assert "bytes" in result["image"]["source"]
    mock_resolve.assert_called_once()


@patch("llama_index.core.base.llms.types.ImageBlock.resolve_image")
def test_content_block_to_bedrock_format_image_assistant(mock_resolve, caplog):
    image_block = ImageBlock(image=b"", image_mimetype="image/png")
    result = _content_block_to_bedrock_format(image_block, MessageRole.ASSISTANT)

    assert result is None
    assert "only supports image blocks for user messages" in caplog.text
    mock_resolve.assert_not_called()


def test_content_block_to_bedrock_format_audio(caplog):
    audio_block = AudioBlock(audio=b"test_audio")
    result = _content_block_to_bedrock_format(audio_block, MessageRole.USER)

    assert result is None
    assert "Audio blocks are not supported" in caplog.text


def test_content_block_to_bedrock_format_unsupported(caplog):
    unsupported_block = object()
    result = _content_block_to_bedrock_format(unsupported_block, MessageRole.USER)

    assert result is None
    assert "Unsupported block type" in caplog.text
    assert str(type(unsupported_block)) in caplog.text


def test_tools_to_converse_tools_with_tool_required():
    """Test that tool_required=True sets toolChoice to {"any": {}}."""

    def search(query: str) -> str:
        """Search for information about a query."""
        return f"Results for {query}"

    tool = FunctionTool.from_defaults(
        fn=search, name="search_tool", description="A tool for searching information"
    )

    result = tools_to_converse_tools([tool], tool_required=True)

    assert "tools" in result
    assert len(result["tools"]) == 1
    assert result["tools"][0]["toolSpec"]["name"] == "search_tool"
    assert result["toolChoice"] == {"any": {}}


def test_tools_to_converse_tools_without_tool_required():
    """Test that tool_required=False sets toolChoice to {"auto": {}}."""

    def search(query: str) -> str:
        """Search for information about a query."""
        return f"Results for {query}"

    tool = FunctionTool.from_defaults(
        fn=search, name="search_tool", description="A tool for searching information"
    )

    result = tools_to_converse_tools([tool], tool_required=False)

    assert "tools" in result
    assert len(result["tools"]) == 1
    assert result["tools"][0]["toolSpec"]["name"] == "search_tool"
    assert result["toolChoice"] == {"auto": {}}


def test_tools_to_converse_tools_with_custom_tool_choice():
    """Test that a custom tool_choice overrides tool_required."""

    def search(query: str) -> str:
        """Search for information about a query."""
        return f"Results for {query}"

    tool = FunctionTool.from_defaults(
        fn=search, name="search_tool", description="A tool for searching information"
    )

    custom_tool_choice = {"specific": {"name": "search_tool"}}
    result = tools_to_converse_tools(
        [tool], tool_choice=custom_tool_choice, tool_required=True
    )

    assert "tools" in result
    assert len(result["tools"]) == 1
    assert result["tools"][0]["toolSpec"]["name"] == "search_tool"
    assert result["toolChoice"] == custom_tool_choice
