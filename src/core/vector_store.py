import requests
import chromadb
from chromadb import EmbeddingFunction
from chromadb.config import Settings

from src.config import (
    EMBEDDING_MODEL,
    SILICONFLOW_API_KEY,
    SILICONFLOW_EMBEDDING_URL,
    VECTOR_DB_PATH,
)


class SiliconFlowEmbeddingFunction(EmbeddingFunction):
    """基于硅基流动 API 的 ChromaDB 嵌入函数。"""

    def __init__(self, api_key: str, model: str, url: str):
        self._api_key = api_key
        self._model = model
        self._url = url
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })

    def __call__(self, input: list[str]) -> list[list[float]]:
        response = self._session.post(
            self._url,
            json={"model": self._model, "input": input},
        )
        response.raise_for_status()
        data = response.json()
        # 按 index 排序以保持输入顺序
        data["data"].sort(key=lambda x: x["index"])
        return [d["embedding"] for d in data["data"]]


class VectorStore:
    """ChromaDB 封装的素材向量存储与搜索。"""

    def __init__(self):
        embed_fn = SiliconFlowEmbeddingFunction(
            api_key=SILICONFLOW_API_KEY,
            model=EMBEDDING_MODEL,
            url=SILICONFLOW_EMBEDDING_URL,
        )
        self.client = chromadb.PersistentClient(
            path=str(VECTOR_DB_PATH),
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name="materials",
            embedding_function=embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def add_material(self, material_id: int, content: str, metadata: dict | None = None):
        """将素材添加到向量存储（嵌入由 API 计算）。"""
        self.collection.add(
            ids=[str(material_id)],
            documents=[content],
            metadatas=[metadata or {}],
        )

    def add_materials_batch(self, items: list[tuple[int, str, dict]]):
        """批量添加多个素材。

        参数：
            items: (material_id, content, metadata) 元组列表
        """
        if not items:
            return
        self.collection.add(
            ids=[str(item[0]) for item in items],
            documents=[item[1] for item in items],
            metadatas=[item[2] for item in items],
        )

    def search(self, query: str, top_k: int = 5):
        """搜索匹配查询文本的素材。"""
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
        )
        return results

    def delete_material(self, material_id: int):
        """从向量存储中删除一个素材。"""
        self.collection.delete(ids=[str(material_id)])
