"""评测数据集（M3c）：查询 + 相关文档标题（doc_id 运行时由 KB 解析）。

相关按"标题"而非"doc_id"标注，因为 doc_id 是随机生成的；
    runner 会用 kb.list_documents() 把标题解析成 doc_id。
    内置集覆盖三类查询：精确关键词 / 语义改写 / 多文档综合。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EvalCase:
    query: str
    relevant_titles: list[str] = field(default_factory=list)


@dataclass
class EvalDataset:
    name: str
    corpus: list[tuple[str, str]]  # (title, content)：评测语料，由调用方负责入库
    cases: list[EvalCase]


def builtin_dataset() -> EvalDataset:
    """内置中文评测集：用于 demo/CI/API 一键对比检索策略。"""
    corpus = [
        (
            "部署指南",
            "在阿里云上部署应用，需配置 ACK 集群、SLB 与 HPA 弹性伸缩，灰度先观察再全量。",
        ),
        ("运维手册", "所有服务部署到阿里云 ACK，容量告警阈值 70%。发布流程：灰度 10% 观察后全量。"),
        (
            "FAQ",
            "如何重置本地缓存？删除 data/cache 目录并重启服务。如何查看日志？看控制台任务卡片。",
        ),
        (
            "记忆指南",
            "分层记忆分三层：短期会话记忆、项目长期事实、用户级向量记忆，按预算注入上下文。",
        ),
    ]
    cases = [
        EvalCase(query="怎么在阿里云上部署应用", relevant_titles=["部署指南"]),
        EvalCase(query="ACK 容量告警阈值是多少", relevant_titles=["运维手册"]),
        EvalCase(query="如何重置本地缓存", relevant_titles=["FAQ"]),
        EvalCase(query="分层记忆分几层", relevant_titles=["记忆指南"]),
        EvalCase(query="部署到云上要走什么流程", relevant_titles=["部署指南", "运维手册"]),
    ]
    return EvalDataset(name="builtin", corpus=corpus, cases=cases)
