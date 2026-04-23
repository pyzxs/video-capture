"""测试向量存储的嵌入函数。"""

import pytest
import responses

from src.core.vector_store import SiliconFlowEmbeddingFunction


@pytest.fixture
def embed_fn():
    return SiliconFlowEmbeddingFunction(
        api_key="test-key",
        model="BAAI/bge-m3",
        url="https://api.siliconflow.cn/v1/embeddings",
    )


@responses.activate
def test_embedding_call_single_input(embed_fn):
    responses.post(
        "https://api.siliconflow.cn/v1/embeddings",
        json={
            "data": [{"index": 0, "embedding": [0.1, 0.2, 0.3]}],
            "model": "BAAI/bge-m3",
            "usage": {"total_tokens": 4},
        },
        status=200,
    )
    result = embed_fn(["你好"])
    assert len(result) == 1
    assert result[0] == pytest.approx([0.1, 0.2, 0.3])


@responses.activate
def test_embedding_call_multiple_inputs(embed_fn):
    responses.post(
        "https://api.siliconflow.cn/v1/embeddings",
        json={
            "data": [
                {"index": 1, "embedding": [0.4, 0.5, 0.6]},
                {"index": 0, "embedding": [0.1, 0.2, 0.3]},
            ],
            "model": "BAAI/bge-m3",
            "usage": {"total_tokens": 8},
        },
        status=200,
    )
    result = embed_fn(["你好", "世界"])
    # 验证按 index 排序
    assert result[0] == pytest.approx([0.1, 0.2, 0.3])
    assert result[1] == pytest.approx([0.4, 0.5, 0.6])


@responses.activate
def test_embedding_sends_correct_headers(embed_fn):
    responses.post(
        "https://api.siliconflow.cn/v1/embeddings",
        json={"data": [{"index": 0, "embedding": [0.1, 0.2, 0.3]}]},
        status=200,
    )
    embed_fn(["test"])
    assert len(responses.calls) == 1
    req = responses.calls[0].request
    assert req.headers["Authorization"] == "Bearer test-key"
    assert req.headers["Content-Type"] == "application/json"


@responses.activate
def test_embedding_api_error(embed_fn):
    responses.post(
        "https://api.siliconflow.cn/v1/embeddings",
        status=401,
    )
    with pytest.raises(Exception):
        embed_fn(["test"])
