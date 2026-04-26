import requests
import chromadb
from chromadb import EmbeddingFunction
from chromadb.config import Settings

from src.config import get_config


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
        data["data"].sort(key=lambda x: x["index"])
        return [d["embedding"] for d in data["data"]]


class VectorStore:
    """ChromaDB 封装的素材向量存储与搜索。"""

    def __init__(self):
        embed_fn = SiliconFlowEmbeddingFunction(
            api_key=get_config("embedding_api_key"),
            model=get_config("embedding_model"),
            url=get_config("embedding_api_base_url"),
        )
        self.client = chromadb.PersistentClient(
            path=str(get_config("vector_db_path")),
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name="materials",
            embedding_function=embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def add_material(self, material_id: int, content: str, metadata: dict | None = None):
        """将素材添加到向量存储。"""
        self.collection.add(
            ids=[str(material_id)],
            documents=[content],
            metadatas=[metadata or {}],
        )

    def add_materials_batch(self, items: list[tuple[int, str, dict]], batch_size: int = 50):
        """批量添加多个素材，自动分块避免请求过大。"""
        if not items:
            return
        total = len(items)
        for i in range(0, total, batch_size):
            batch = items[i : i + batch_size]
            self.collection.add(
                ids=[str(item[0]) for item in batch],
                documents=[item[1] for item in batch],
                metadatas=[item[2] for item in batch],
            )

    def search(self, query: str, top_k: int = 5, where: dict | None = None):
        """搜索匹配查询文本的素材。"""
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where,
        )
        return results

    def delete_material(self, material_id: int):
        """从向量存储中删除一个素材。"""
        self.collection.delete(ids=[str(material_id)])
