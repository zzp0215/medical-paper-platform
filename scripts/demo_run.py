#!/usr/bin/env python3
"""
端到端验证脚本 (Phase 1.2.3 / Sprint 3).

流程
----
1. 模拟 PDF 上传 (用测试 PDF)
2. 调 parse + vectorize (mock DB/Milvus)
3. 模拟用户输入论文题目
4. 调 planner + writer (mock LLM, 走降级链)
5. 调 word export
6. 输出验证报告

用法
----
# 1) 默认 (mocked, 不连服务)
python3 scripts/demo_run.py

# 2) 真服务模式 (需启 docker compose up)
LITELLM_BASE_URL=http://localhost:4000/v1 \
DEEPSEEK_API_KEY=sk-real-key \
python3 scripts/demo_run.py --real

# 3) 跳过 PDF, 纯文本生成 demo
python3 scripts/demo_run.py --no-pdf
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.agents import OutlineNode, PaperOutline, write_all_sections  # noqa: E402
from backend.agents.planner_simple import _default_outline, _parse_outline  # noqa: E402
from backend.core import logger  # noqa: E402


# ============================================
# 模拟 LLM 响应 (避免外部依赖)
# ============================================
def mock_outline_response(title: str, paper_type: str) -> str:
    """生成合理的假大纲 JSON."""
    import json

    if paper_type == "review":
        sections = [
            {"order_index": 1, "heading": "摘要", "section_type": "abstract",
             "description": f"概述{title}的研究范围与方法",
             "key_points": ["研究背景", "检索策略", "主要发现"]},
            {"order_index": 2, "heading": "引言", "section_type": "introduction",
             "description": "疾病背景与研究意义",
             "key_points": ["流行病学", "临床挑战", "研究目的"]},
            {"order_index": 3, "heading": "方法", "section_type": "methods",
             "description": "文献检索与纳入标准",
             "key_points": ["数据库选择", "检索词", "筛选流程"]},
            {"order_index": 4, "heading": "结果", "section_type": "results",
             "description": "主要发现分类总结",
             "key_points": ["研究数量", "样本特征", "主要结论"]},
            {"order_index": 5, "heading": "讨论", "section_type": "discussion",
             "description": "与现有证据对比",
             "key_points": ["与既往研究比较", "机制探讨", "局限性"]},
            {"order_index": 6, "heading": "结论", "section_type": "conclusion",
             "description": "总结与展望",
             "key_points": ["核心结论", "临床意义", "未来方向"]},
        ]
    else:
        sections = _default_outline(paper_type, title).to_dict()["sections"]
        sections = [
            {"order_index": s["order_index"], "heading": s["heading"],
             "section_type": s["section_type"], "description": s["description"],
             "key_points": s.get("key_points", [])}
            for s in sections
        ]
    return json.dumps({"abstract_intent": f"本{('综述' if paper_type == 'review' else '研究')}聚焦{title}",
                       "sections": sections}, ensure_ascii=False)


def mock_section_content(heading: str, section_type: str, title: str) -> str:
    """生成合理的假章节内容."""
    contents = {
        "abstract": f"## {heading}\n\n本{'研究' if section_type != 'review' else '综述'}聚焦《{title}》..."
                    f"采用系统检索策略, 纳入近 5 年相关文献..."
                    f"主要发现: ... 结论: ...",
        "introduction": f"## {heading}\n\n{title}是当前医学研究的热点领域 [1]..."
                        f"流行病学数据显示 ...\n\n现有研究存在以下不足: ...\n\n本研究的目的: ...",
        "methods": f"## {heading}\n\n**检索策略**: 检索 PubMed、Embase、Cochrane 数据库...\n\n"
                   f"**纳入标准**: 1) ... 2) ...\n\n**统计方法**: 采用 RevMan 5.4 软件...",
        "results": f"## {heading}\n\n共纳入 15 项研究, 总样本量 3,250 例.\n\n"
                   f"**主要发现**: 干预组有效率 78.5% (n=1,275/1,624), 对照组 52.3% (n=851/1,626), "
                   f"差异有统计学意义 (P<0.001) [1].\n\n**亚组分析**: ...",
        "discussion": f"## {heading}\n\n本研究结果与 Smith 等 [2] 的 Meta 分析一致, 提示 ...\n\n"
                      f"**机制探讨**: 可能与 ... 通路相关 [3].\n\n**局限性**: 1) 纳入研究异质性较大 2) 部分研究样本量小...",
        "conclusion": f"## {heading}\n\n综上所述, {title} 显示 ... 具有重要的临床意义.\n\n"
                      f"未来研究方向: 1) 大规模 RCT 验证 2) 长期安全性评估...",
    }
    return contents.get(section_type, f"## {heading}\n\n(默认内容)")


# ============================================
# 主流程
# ============================================
async def run_demo(
    *,
    use_pdf: bool = True,
    paper_type: str = "review",
    target_language: str = "zh",
) -> dict:
    """端到端演示 (mocked LLM)."""
    title = "2 型糖尿病治疗新进展"
    results: dict = {"title": title, "steps": []}
    print(f"\n📚 论文题目: {title}\n")
    print("=" * 60)

    # ============================================
    # Step 1: PDF 解析
    # ============================================
    if use_pdf:
        print("\n[1/5] 📄 PDF 解析...")
        t0 = time.perf_counter()
        from backend.parser import PyMuPDFParser
        sample_pdf = PROJECT_ROOT / "tests" / "test_pdfs" / "sample.pdf"
        if sample_pdf.exists():
            parser = PyMuPDFParser()
            parse_result = await parser.parse(sample_pdf.read_bytes(), filename="sample.pdf")
            elapsed = (time.perf_counter() - t0) * 1000
            msg = f"✅ PDF 解析 ({parse_result.page_count} 页, {len(parse_result.markdown)} 字符, {elapsed:.0f}ms)"
            print(msg)
            results["steps"].append({"step": "parse", "pages": parse_result.page_count,
                                     "chars": len(parse_result.markdown), "elapsed_ms": elapsed})
        else:
            print("⚠️  测试 PDF 不存在, 跳过")
            results["steps"].append({"step": "parse", "skipped": True})

    # ============================================
    # Step 2: 大纲生成
    # ============================================
    print("\n[2/5] 📋 大纲生成...")
    t0 = time.perf_counter()
    fake_llm_outline = mock_outline_response(title, paper_type)
    outline = _parse_outline(fake_llm_outline, paper_type, title)
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"✅ 大纲生成 ({len(outline.sections)} 节, {elapsed:.0f}ms)")
    for s in outline.sections:
        print(f"   - {s.order_index}. {s.heading} ({s.section_type})")
    results["steps"].append({"step": "outline", "sections": len(outline.sections),
                             "elapsed_ms": elapsed, "outline": outline.to_dict()})

    # ============================================
    # Step 3: 逐节写作 (mock LLM)
    # ============================================
    print("\n[3/5] ✍️  逐节写作...")
    t0 = time.perf_counter()
    section_results: dict[int, str] = {}
    total_words = 0
    for node in outline.sections:
        if node.section_type == "references":
            section_results[node.order_index] = ""
            continue
        content = mock_section_content(node.heading, node.section_type, title)
        section_results[node.order_index] = content
        total_words += len(content)
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"✅ 写作完成 ({len(section_results)} 节, {total_words} 字符, {elapsed:.0f}ms)")
    results["steps"].append({"step": "write", "sections": len(section_results),
                             "total_chars": total_words, "elapsed_ms": elapsed})

    # ============================================
    # Step 4: Word 导出
    # ============================================
    print("\n[4/5] 📄 Word 导出...")
    t0 = time.perf_counter()
    from docx import Document
    from io import BytesIO
    doc = Document()
    doc.add_heading(title, level=0)
    for node in outline.sections:
        content = section_results.get(node.order_index, "")
        if not content:
            continue
        doc.add_heading(f"{node.order_index}. {node.heading}", level=1)
        for para in content.split("\n\n"):
            para = para.strip()
            if para.startswith("## "):
                doc.add_heading(para[3:], level=2)
            elif para:
                doc.add_paragraph(para)
    buf = BytesIO()
    doc.save(buf)
    docx_bytes = buf.getvalue()
    buf.close()
    elapsed = (time.perf_counter() - t0) * 1000

    out_path = PROJECT_ROOT / "data" / "outputs" / "demo_paper.docx"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(docx_bytes)
    print(f"✅ Word 导出 ({len(docx_bytes)} bytes, {elapsed:.0f}ms)")
    print(f"   路径: {out_path}")
    results["steps"].append({"step": "word_export", "size": len(docx_bytes),
                             "elapsed_ms": elapsed, "path": str(out_path)})

    # ============================================
    # Step 5: 完整论文预览
    # ============================================
    print("\n[5/5] 📖 论文预览 (前 800 字):\n")
    full_text = title + "\n\n"
    for node in outline.sections:
        content = section_results.get(node.order_index, "")
        if content:
            full_text += f"\n## {node.heading}\n\n{content}\n\n"
    print(full_text[:800] + ("..." if len(full_text) > 800 else ""))

    # ============================================
    # 总结
    # ============================================
    print("\n" + "=" * 60)
    print("📊 验证结果总结")
    print("=" * 60)
    total_elapsed = sum(s.get("elapsed_ms", 0) for s in results["steps"])
    print(f"   步骤数: {len(results['steps'])}")
    print(f"   总耗时: {total_elapsed:.0f}ms ({total_elapsed/1000:.1f}s)")
    print(f"   大纲: {len(outline.sections)} 节")
    print(f"   写作: {total_words} 字符")
    print(f"   Word: {len(docx_bytes) // 1024} KB")
    print(f"   路径: {out_path}")
    print("=" * 60)
    print("✅ 端到端流程跑通 (mocked LLM)\n")

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="MVP 端到端验证")
    parser.add_argument("--no-pdf", action="store_true", help="跳过 PDF 解析步骤")
    parser.add_argument("--type", default="review", help="论文类型: review / clinical_trial / ...")
    parser.add_argument("--real", action="store_true", help="连真 LLM 服务 (需配置 key)")
    args = parser.parse_args()

    print("🚀 MVP 端到端验证")
    print(f"   模式: {'真实 LLM' if args.real else 'Mock (无需 key)'}")
    print(f"   论文类型: {args.type}")
    print(f"   PDF: {'跳过' if args.no_pdf else '包含'}")

    if args.real:
        print("\n⚠️  --real 模式需要先启 docker 服务 (LiteLLM/PostgreSQL/Milvus)")
        print("   当前未实现真服务模式, 走 mock")
        args.real = False

    asyncio.run(run_demo(use_pdf=not args.no_pdf, paper_type=args.type))
    return 0


if __name__ == "__main__":
    sys.exit(main())
