"""Video-Capture CLI — 视频处理、搜索、混剪生成与配音。"""

from pathlib import Path

import typer
import uvicorn

app = typer.Typer(help="视频字幕提取、语义搜索、混剪生成与 AI 配音工具")


@app.command()
def process(
    video: str = typer.Argument(..., help="视频文件路径"),
    language: str = typer.Option("zh", "--language", "-l", help="ASR 语言代码"),
):
    """处理视频：提取时间轴 → 生成段落 → 存储 → 向量化。"""
    from src.pipelines.ingest import process_video as _process

    try:
        result = _process(video, language=language)
        typer.echo(f"\n完成。素材数={result['material_count']}")
    except Exception as e:
        typer.echo(f"处理失败：{e}", err=True)
        raise typer.Exit(1)


@app.command()
def search(
    query: str = typer.Argument(..., help="搜索文本"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="返回结果数"),
    width: int | None = typer.Option(None, "--width", help="筛选：视频宽度"),
    height: int | None = typer.Option(None, "--height", help="筛选：视频高度"),
    fps: float | None = typer.Option(None, "--fps", help="筛选：视频帧率"),
):
    """搜索已索引的素材内容。"""
    from src.db.engine import init_db
    from src.services.search import search_materials

    init_db()
    results = search_materials(query, top_k=top_k, frame_width=width, frame_height=height, frame_rate=fps)

    if not results:
        typer.echo("未找到匹配内容。")
        raise typer.Exit()

    typer.echo(f"\n找到 {len(results)} 条结果：\n")
    for i, r in enumerate(results, 1):
        typer.echo(f"  [{i}] 素材 #{r['material_id']}")
        typer.echo(f"      时间：{r['start_time']:.1f}s → {r['end_time']:.1f}s")
        typer.echo(f"      分辨率：{r['frame_width']}x{r['frame_height']} @ {r['frame_rate']}fps")
        typer.echo(f"      文本：{r['content'][:120]}")
        typer.echo()


@app.command()
def generate(
    query: str = typer.Argument(..., help="内容描述关键词"),
    output: str | None = typer.Option(None, "--output", "-o", help="输出视频路径"),
    style: str = typer.Option("自然流畅", "--style", help="LLM 扩写风格"),
    width: int | None = typer.Option(None, "--width", help="筛选：视频宽度"),
    height: int | None = typer.Option(None, "--height", help="筛选：视频高度"),
    fps: float | None = typer.Option(None, "--fps", help="筛选：视频帧率"),
):
    """LLM 扩写 + 向量检索 + 混剪拼接 + TTS 配音。"""
    from src.pipelines.generate import search_and_generate

    try:
        result = search_and_generate(
            query=query,
            output_path=output,
            frame_width=width,
            frame_height=height,
            frame_rate=fps,
        )
        if "error" in result:
            typer.echo(f"错误：{result['error']}", err=True)
            raise typer.Exit(1)
        typer.echo(f"\n输出视频：{result.get('output_video', 'N/A')}")
    except Exception as e:
        typer.echo(f"生成失败：{e}", err=True)
        raise typer.Exit(1)


@app.command()
def dub(
    video: str = typer.Argument(..., help="源视频路径"),
    text: str = typer.Argument(None, help="配音文本"),
    text_file: str | None = typer.Option(None, "--text-file", "-f", help="从文件读取配音文本"),
    voice: str | None = typer.Option(None, "--voice", help="TTS 音色"),
    output: str | None = typer.Option(None, "--output", "-o", help="输出视频路径"),
):
    """文本合成语音并替换视频音轨。"""
    from src.services.tts import dub_from_text

    if text_file:
        text = Path(text_file).read_text(encoding="utf-8").strip()
    if not text:
        typer.echo("错误：文本内容为空。", err=True)
        raise typer.Exit(1)

    try:
        result = dub_from_text(video_path=video, text=text, voice=voice, output_path=output)
        typer.echo(f"\n配音视频：{result}")
    except Exception as e:
        typer.echo(f"配音失败：{e}", err=True)
        raise typer.Exit(1)


@app.command()
def web(
    host: str = typer.Option("127.0.0.1", "--host", help="监听地址"),
    port: int = typer.Option(8090, "--port", "-p", help="监听端口"),
    reload: bool = typer.Option(True, "--reload", help="热重载"),
):
    """启动 Web 服务（FastAPI + 前端）。"""
    typer.echo(f"启动 Web 服务: http://{host}:{port}")
    uvicorn.run("src.api.app:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
