from src.db.engine import get_session
from src.db.vector import VectorStore
from src.db.models import Material
from src.logger import get_logger

logger = get_logger("services.search")

_BGE_QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："

def _format_material(m) -> dict:
    return {
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
        "status": getattr(m, "status", 1),
    }


def search_materials(
    query: str,
    top_k: int = 5,
    frame_width: int | None = None,
    frame_height: int | None = None,
    frame_rate: float | None = None,
) -> list[dict]:
    """通过向量相似度搜索匹配查询的素材，可选按帧参数筛选。

    向量搜索无结果时自动回退到关键词模糊匹配（LIKE），
    确保人名、专有名词等也能被找到。

    参数：
        query: 搜索文本
        top_k: 返回结果数
        frame_width: 筛选目标视频宽度（像素）
        frame_height: 筛选目标视频高度（像素）
        frame_rate: 筛选目标视频帧率

    返回包含素材内容、文件路径和时间信息的字典列表，
    按相关性排序（最佳匹配在前）。
    """
    # 构建元数据过滤条件
    where = None
    filters = {}
    if frame_width is not None:
        filters["frame_width"] = frame_width
    if frame_height is not None:
        filters["frame_height"] = frame_height
    if frame_rate is not None:
        filters["frame_rate"] = frame_rate
    if len(filters) == 1:
        where = filters
    elif len(filters) > 1:
        where = {"$and": [{k: v} for k, v in filters.items()]}

    if not query or not query.strip():
        return []

    prefixed_query = f"{_BGE_QUERY_PREFIX}{query}"
    store = VectorStore()
    results = store.search(prefixed_query, top_k=top_k, where=where or None)

    # 向量搜索结果（仅保留距离小的高质量匹配）
    vec_materials: list[dict] = []
    if results.get("ids") and results["ids"][0]:
        ids = results["ids"][0]
        distances = results.get("distances", [[]])[0]

        for id_, dist in zip(ids, distances):
            logger.debug("material #%d distance=%.4f", id_, dist)

        good_ids = [
            int(id_)
            for id_, dist in zip(ids, distances)
            if dist < 0.7
        ]
        if good_ids:
            session2 = get_session()
            try:
                materials = (
                    session2.query(Material)
                    .filter(Material.id.in_(good_ids), Material.status == 1)
                    .all()
                )
                id_to_material = {m.id: m for m in materials}
                sorted_materials = [id_to_material[mid] for mid in good_ids if mid in id_to_material]
                vec_materials = [_format_material(m) for m in sorted_materials]
            finally:
                session2.close()

    # 关键词搜索（仅 status=1 的有效素材，作为向量搜索的补充）
    session = get_session()
    try:
        q = f"%{query.strip()}%"
        kw_query = session.query(Material).filter(
            Material.content.like(q),
            Material.status == 1,
        )
        if frame_width is not None:
            kw_query = kw_query.filter(Material.frame_width == frame_width)
        if frame_height is not None:
            kw_query = kw_query.filter(Material.frame_height == frame_height)
        if frame_rate is not None:
            kw_query = kw_query.filter(Material.frame_rate == frame_rate)
        kw_materials = [_format_material(m) for m in kw_query.limit(top_k).all()]
    finally:
        session.close()

    # 合并：向量结果优先，关键词补充（去重）
    seen = {m["material_id"] for m in vec_materials}
    merged = list(vec_materials)
    for m in kw_materials:
        if m["material_id"] not in seen:
            merged.append(m)

    return merged[:top_k]
