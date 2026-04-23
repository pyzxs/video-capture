from src.core.database import get_session
from src.core.vector_store import VectorStore
from src.models.models import Material


def search_materials(query: str, top_k: int = 5) -> list[dict]:
    """通过向量相似度搜索匹配查询的素材。

    返回包含素材内容、文件路径和时间信息的字典列表，
    按相关性排序（最佳匹配在前）。
    """
    store = VectorStore()
    results = store.search(query, top_k=top_k)

    if not results["ids"] or not results["ids"][0]:
        return []

    material_ids = [int(id_) for id_ in results["ids"][0]]

    session = get_session()
    try:
        materials = (
            session.query(Material)
            .filter(Material.id.in_(material_ids))
            .all()
        )

        id_to_material = {m.id: m for m in materials}
        sorted_materials = [id_to_material[mid] for mid in material_ids if mid in id_to_material]

        return [
            {
                "material_id": m.id,
                "type": m.type,
                "content": m.content,
                "start_time": m.start_time,
                "end_time": m.end_time,
                "frame_width": m.frame_width,
                "frame_height": m.frame_height,
                "frame_rate": m.frame_rate,
                "filename": m.filename,
                "filepath": m.filepath,
            }
            for m in sorted_materials
        ]
    finally:
        session.close()
