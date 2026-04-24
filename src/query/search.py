from src.core.database import get_session
from src.core.vector_store import VectorStore
from src.models.models import Material


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
    where = {}
    if frame_width is not None:
        where["frame_width"] = frame_width
    if frame_height is not None:
        where["frame_height"] = frame_height
    if frame_rate is not None:
        where["frame_rate"] = frame_rate

    if not query or not query.strip():
        return []

    store = VectorStore()
    results = store.search(query, top_k=top_k, where=where or None)

    # 关键词搜索（全量，不受向量影响）
    session = get_session()
    try:
        q = f"%{query.strip()}%"
        kw_query = session.query(Material).filter(Material.content.like(q))
        if frame_width is not None:
            kw_query = kw_query.filter(Material.frame_width == frame_width)
        if frame_height is not None:
            kw_query = kw_query.filter(Material.frame_height == frame_height)
        if frame_rate is not None:
            kw_query = kw_query.filter(Material.frame_rate == frame_rate)
        kw_materials = [_format_material(m) for m in kw_query.limit(top_k).all()]
    finally:
        session.close()

    # 向量搜索结果（仅保留距离小的高质量匹配）
    vec_materials: list[dict] = []
    if results.get("ids") and results["ids"][0]:
        ids = results["ids"][0]
        distances = results.get("distances", [[]])[0]

        # 打印实际距离值便于调优阈值
        for id_, dist in zip(ids, distances):
            print(f"  [debug] material #{id_} distance={dist:.4f}")

        good_ids = [
            int(id_)
            for id_, dist in zip(ids, distances)
            if dist < 0.6
        ]
        if good_ids:
            session2 = get_session()
            try:
                materials = (
                    session2.query(Material)
                    .filter(Material.id.in_(good_ids))
                    .all()
                )
                id_to_material = {m.id: m for m in materials}
                sorted_materials = [id_to_material[mid] for mid in good_ids if mid in id_to_material]
                vec_materials = [_format_material(m) for m in sorted_materials]
            finally:
                session2.close()

    # 合并：关键词优先，再补充高质量向量结果（去重）
    seen = {m["material_id"] for m in kw_materials}
    merged = list(kw_materials)
    for m in vec_materials:
        if m["material_id"] not in seen:
            merged.append(m)

    return merged[:top_k]
