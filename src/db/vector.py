import requests
import chromadb
from chromadb import EmbeddingFunction
from chromadb.config import Settings

from src.config import get_config


class SiliconFlowEmbeddingFunction(EmbeddingFunction):
    """通过 CMS 代理的 ChromaDB 嵌入函数。"""

    def __init__(self, api_key: str, model: str, url: str):
        self._api_key = api_key
        self._model = model
        self._proxy_url = url  # CMS proxy URL
        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json",
        })

    def __call__(self, input: list[str]) -> list[list[float]]:
        headers = dict(self._session.headers)
        api_key = self._api_key
        if api_key:
            headers["X-Api-Key"] = api_key

        response = self._session.post(
            self._proxy_url,
            json={"model": self._model, "input": input},
            headers=headers,
        )
        if response.status_code == 402:
            raise RuntimeError("CMS 额度不足，请充值")
        response.raise_for_status()
        result = response.json()
        emb_data = result.get("data", result)
        emb_data["data"].sort(key=lambda x: x["index"])
        return [d["embedding"] for d in emb_data["data"]]


class VectorStore:
    """ChromaDB 封装的素材向量存储与搜索。通过 CMS 代理调用 Embedding API。"""

    def __init__(self):
        cms_url = get_config("cms_base_url")
        embed_fn = SiliconFlowEmbeddingFunction(
            api_key=get_config("api_key"),
            model=get_config("embedding_model"),
            url=f"{cms_url}/api/proxy/embedding",
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
        self.collection.upsert(
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
            self.collection.upsert(
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
