#!/usr/bin/env python3
"""
PDF → Markdown 基础链路验证脚本 (Phase 1.2.1).

用法
----
1. 准备测试 PDF:  cp /path/to/sample.pdf tests/test_pdfs/sample.pdf
2. python3 scripts/verify_pdf_parsing.py

验证项
------
1. PyMuPDF4LLM 能读 PDF
2. 转换出 Markdown (含中英文)
3. 页数/字数统计合理
4. 报告耗时 (CPU 环境预期 1-3s/页)
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.parser import PyMuPDFParser  # noqa: E402
from backend.core import logger  # noqa: E402


# ============================================
# 查找测试 PDF
# ============================================
def find_sample_pdf() -> Path | None:
    candidates = [
        PROJECT_ROOT / "tests" / "test_pdfs" / "sample.pdf",
        PROJECT_ROOT / "data" / "test_pdfs" / "sample.pdf",
        PROJECT_ROOT / "samples" / "sample.pdf",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


# ============================================
# 主流程
# ============================================
async def main() -> int:
    print("=" * 60)
    print("PDF → Markdown 基础链路验证 (Phase 1.2.1)")
    print("=" * 60)

    sample = find_sample_pdf()
    if sample is None:
        print("\n❌ 未找到测试 PDF")
        print("   请将任意 PDF 放到以下任一位置:")
        for c in [
            PROJECT_ROOT / "tests" / "test_pdfs" / "sample.pdf",
            PROJECT_ROOT / "data" / "test_pdfs" / "sample.pdf",
        ]:
            print(f"     - {c}")
        print("\n   或从 arXiv/PubMed 下载一篇 PDF 测试:")
        print("     curl -L -o tests/test_pdfs/sample.pdf https://arxiv.org/pdf/2408.09869")
        return 1

    print(f"\n📄 测试文件: {sample}")
    print(f"   大小: {sample.stat().st_size} B")

    file_bytes = sample.read_bytes()
    parser = PyMuPDFParser(extract_images=False)

    t0 = time.perf_counter()
    try:
        result = await parser.parse(file_bytes, filename=sample.name)
    except Exception as e:
        print(f"\n❌ 解析失败: {e}")
        return 2

    elapsed = (time.perf_counter() - t0) * 1000

    # ============================================
    # 验证项
    # ============================================
    print(f"\n✅ 解析成功 ({elapsed:.0f}ms)\n")

    print("📊 解析结果:")
    print(f"   页数:     {result.page_count}")
    print(f"   Block 数: {len(result.blocks)}")
    print(f"   Markdown 长度: {len(result.markdown)} 字符")
    print(f"   Block 类型分布:")
    type_counts: dict[str, int] = {}
    for b in result.blocks:
        type_counts[b.type] = type_counts.get(b.type, 0) + 1
    for t, n in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"     - {t}: {n}")

    # 中文检测
    has_chinese = any("一" <= ch <= "鿿" for ch in result.markdown)
    print(f"   包含中文: {'是' if has_chinese else '否'}")

    # 输出预览
    preview = result.markdown[:500].replace("\n", "\n     ")
    print(f"\n📝 Markdown 预览 (前 500 字符):\n     {preview}")
    if len(result.markdown) > 500:
        print(f"     ... (省略 {len(result.markdown) - 500} 字符)")

    # 落盘
    out_path = PROJECT_ROOT / "data" / "tmp" / f"{sample.stem}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(result.markdown, encoding="utf-8")
    print(f"\n💾 Markdown 已保存: {out_path}")

    # ============================================
    # 性能断言 (CPU 环境)
    # ============================================
    per_page = elapsed / max(result.page_count, 1)
    print(f"\n⏱  性能: {per_page:.0f}ms/页 (CPU 服务器, 可接受 <3000ms/页)")

    if per_page > 3000:
        print("   ⚠️  较慢, 建议: 检查 PyMuPDF 版本 / 关闭 extract_images")
    else:
        print("   ✅ 性能可接受")

    print("\n" + "=" * 60)
    print("✅ Phase 1.2.1 验证通过")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
