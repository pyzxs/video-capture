"""Video-Capture 命令行工具 — 字幕提取、搜索、字幕生成与配音。"""

import argparse
import sys
from pathlib import Path

from src.core.database import init_db
from src.pipeline import process_video, search_and_generate
from src.query.search import search_materials


def cmd_process(args):
    """处理视频：提取时间轴 → 生成段落 → 存储 → 向量化。"""
    try:
        result = process_video(args.video, language=args.language)
        print(f"\n完成。素材数={result['material_count']}")
    except FileNotFoundError as e:
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"处理失败：{e}", file=sys.stderr)
        sys.exit(1)


def cmd_search(args):
    """搜索已索引的内容并显示结果。"""
    init_db()
    results = search_materials(args.query, top_k=args.top_k)

    if not results:
        print("未找到匹配内容。")
        return

    print(f"\n找到 {len(results)} 条结果：\n")
    for i, r in enumerate(results, 1):
        print(f"  [{i}] 段落 #{r['paragraph_id']}（视频：{r['video_filename']}）")
        print(f"      时间：{r['start_time']:.1f} 秒 → {r['end_time']:.1f} 秒")
        print(f"      文本：{r['content'][:120]}{'...' if len(r['content']) > 120 else ''}")
        print()


def cmd_generate(args):
    """搜索、LLM 优化并生成带字幕的视频。"""
    try:
        result = search_and_generate(
            query=args.query,
            output_path=args.output,
        )
        if "error" in result:
            print(f"错误：{result['error']}", file=sys.stderr)
            if "srt_path" in result:
                print(f"  （SRT 文件已生成：{result['srt_path']}）")
            sys.exit(1)
        print(f"\n输出视频：{result.get('output_video', 'N/A')}")
        print(f"SRT 文件：{result.get('srt_path', 'N/A')}")
    except Exception as e:
        print(f"生成失败：{e}", file=sys.stderr)
        sys.exit(1)


def cmd_dub(args):
    """文本合成语音并替换视频音轨。"""
    from src.tts.cosyvoice import dub_from_text

    try:
        if args.text_file:
            text = Path(args.text_file).read_text(encoding="utf-8").strip()
        else:
            text = args.text

        if not text:
            print("错误：文本内容为空。", file=sys.stderr)
            sys.exit(1)

        result = dub_from_text(
            video_path=args.video,
            text=text,
            voice=args.voice,
            output_path=args.output,
        )
        print(f"\n配音视频：{result}")
    except Exception as e:
        print(f"配音失败：{e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="视频字幕提取、语义搜索、字幕重生成与 AI 配音工具",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # process
    p_process = subparsers.add_parser("process", help="处理视频的完整流水线")
    p_process.add_argument("video", help="视频文件路径")
    p_process.add_argument("-l", "--language", default="zh", help="ASR 语言代码（默认：zh）")
    p_process.set_defaults(func=cmd_process)

    # search
    p_search = subparsers.add_parser("search", help="搜索已索引的内容")
    p_search.add_argument("query", help="搜索文本")
    p_search.add_argument("-k", "--top-k", type=int, default=5, help="返回结果数（默认：5）")
    p_search.set_defaults(func=cmd_search)

    # generate
    p_gen = subparsers.add_parser("generate", help="搜索、优化并生成带字幕的视频")
    p_gen.add_argument("query", help="内容搜索关键词")
    p_gen.add_argument("--output", "-o", help="输出视频路径")
    p_gen.add_argument("--style", default="自然流畅", help="LLM 优化风格（默认：自然流畅）")
    p_gen.set_defaults(func=cmd_generate)

    # dub
    p_dub = subparsers.add_parser("dub", help="文本合成语音并替换视频音轨")
    p_dub.add_argument("video", help="源视频路径")
    p_dub.add_argument("text", nargs="?", help="配音文本")
    p_dub.add_argument("-f", "--text-file", help="从文件读取配音文本")
    p_dub.add_argument("--voice", help="TTS 音色（默认使用配置 TTS_VOICE）")
    p_dub.add_argument("-o", "--output", help="输出视频路径")
    p_dub.set_defaults(func=cmd_dub)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
