"""
LangGraph Hello World (Phase 1.2.3).

演示 LangGraph 最基础的:
- TypedDict 状态
- 节点函数 (Node)
- 边 (Edge) + 条件边 (Conditional Edge)
- 调用 LLM (走我们的 LLMRouter → LiteLLM → DeepSeek)
- 编译 + 调用

流程图
------
       START
         |
         v
      [think]  ← 调 LLM 生成思路
         |
         v
      [should_continue?]  ← 条件路由
        / \
   yes  /   \  no
      v     v
  [refine] [finalize]
      \     /
       \   /
        v v
        END

运行
----
# 1. 启 LiteLLM (需 docker compose up -d litellm)
# 2. python3 examples/hello_langgraph.py

测试 (不连真 LLM, mock)
----
pytest tests/test_langgraph_hello.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from typing import Literal, TypedDict

# 项目根加入 path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from langgraph.graph import END, START, StateGraph  # noqa: E402

from backend.core import logger  # noqa: E402
from backend.llm import ChatMessage, ChatRequest, LLMRouter  # noqa: E402


# ============================================
# 状态定义
# ============================================
class HelloState(TypedDict, total=False):
    """最小可用的 LangGraph 状态."""

    question: str
    thought: str
    answer: str
    iterations: int
    max_iterations: int


# ============================================
# 节点
# ============================================
async def think_node(state: HelloState) -> dict:
    """调用 LLM 生成 '思路'."""
    question = state["question"]
    logger.info("[think] question={!r}", question[:50])

    async with LLMRouter() as router:
        resp = await router.chat(
            request=ChatRequest(
                messages=[
                    ChatMessage(
                        role="system",
                        content="你是一个医学助手, 用一句话回答用户问题 (50 字以内).",
                    ),
                    ChatMessage(role="user", content=question),
                ],
                temperature=0.3,
                max_tokens=128,
            ),
            scenario="default",
        )
    # think 不自增, 由 refine 自增 (实现 should_refine 的次数控制)
    return {"thought": resp.content}


async def refine_node(state: HelloState) -> dict:
    """refine 阶段: 让 LLM 优化答案."""
    logger.info("[refine] 优化答案")
    async with LLMRouter() as router:
        resp = await router.chat(
            request=ChatRequest(
                messages=[
                    ChatMessage(
                        role="system",
                        content="请把答案改得更专业、更准确 (100 字以内).",
                    ),
                    ChatMessage(role="user", content=state["thought"]),
                ],
                temperature=0.2,
                max_tokens=256,
            ),
            scenario="polish",  # 走 quality_first 链路
        )
    return {
        "answer": resp.content,
        "iterations": state.get("iterations", 0) + 1,
    }


async def finalize_node(state: HelloState) -> dict:
    """finalize 阶段: 简单包装."""
    return {
        "answer": f"💡 {state.get('thought', '')}\n\n📋 精炼: {state.get('answer', state.get('thought', ''))}",
    }


# ============================================
# 条件路由
# ============================================
def should_refine(state: HelloState) -> Literal["refine", "finalize"]:
    """决定是否继续 refine.

    约定: max_iterations = 期望 refine 的次数
    - max_iterations=0: 跳过 refine, think 后直接 finalize
    - max_iterations=1: refine 一次
    - iterations 由 refine_node 自增, think_node 不动
    """
    iters = state.get("iterations", 0)
    max_iters = state.get("max_iterations", 1)
    if iters < max_iters:
        return "refine"
    return "finalize"


# ============================================
# 构图
# ============================================
def build_graph() -> "StateGraph":
    workflow = StateGraph(HelloState)

    # 节点
    workflow.add_node("think", think_node)
    workflow.add_node("refine", refine_node)
    workflow.add_node("finalize", finalize_node)

    # 边
    workflow.add_edge(START, "think")
    workflow.add_conditional_edges(
        "think",
        should_refine,
        {
            "refine": "refine",
            "finalize": "finalize",
        },
    )
    workflow.add_edge("refine", "finalize")
    workflow.add_edge("finalize", END)

    return workflow.compile()


# ============================================
# 入口
# ============================================
async def main() -> None:
    print("=" * 60)
    print("LangGraph Hello World (Phase 1.2.3)")
    print("=" * 60)

    question = "什么是 2 型糖尿病?"
    print(f"\n❓ 问题: {question}\n")

    graph = build_graph()
    result = await graph.ainvoke(
        {
            "question": question,
            "iterations": 0,
            "max_iterations": 1,
        }
    )

    print("\n📊 最终结果:")
    for k, v in result.items():
        print(f"  {k}: {v}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
