"""Rule-based task classifier for prompt intent detection."""
from __future__ import annotations


# Task type → keyword patterns (checked against lowercased prompt)
TASK_PATTERNS: dict[str, list[str]] = {
    "debugging": [
        "bug", "error", "fix", "broken", "crash", "fail", "traceback",
        "exception", "issue", "not working", "doesn't work", "debug",
        "wrong", "unexpected", "排查", "报错", "出错", "修复", "崩溃",
        "问题", "不工作", "不对", "异常",
    ],
    "coding": [
        "implement", "write", "create", "add", "function", "class",
        "method", "code", "script", "build", "make", "feature",
        "实现", "写", "创建", "添加", "功能", "代码", "脚本",
        "帮我写", "帮我改", "帮我加",
    ],
    "architecture": [
        "architect", "design", "plan", "structure", "refactor",
        "pattern", "system", "schema", "upgrade", "migration",
        "roadmap", "proposal", "方案", "架构", "设计", "重构",
        "规划", "升级", "迁移",
    ],
    "explanation": [
        "explain", "what is", "how does", "why", "understand",
        "meaning", "difference", "compare", "解释", "什么是",
        "为什么", "怎么", "区别", "对比", "理解",
    ],
    "configuration": [
        "config", "setup", "install", "setting", "env", "deploy",
        "docker", "yaml", "json", "permission", "hook",
        "配置", "安装", "设置", "部署", "环境",
    ],
    "documentation": [
        "document", "readme", "doc", "comment", "describe",
        "spec", "write up", "文档", "注释", "说明", "描述",
        "记录", "写入", "整理",
    ],
    "review": [
        "review", "check", "audit", "inspect", "look at",
        "examine", "verify", "审计", "检查", "审查", "确认",
        "看看", "先看", "先读",
    ],
}

# Preference description fragments → affinity tags used for matching
# These map to substrings found in preference descriptions
TASK_AFFINITY: dict[str, list[str]] = {
    "debugging": [
        "evidence", "diagnosis", "concise",
    ],
    "coding": [
        "concise", "modular", "compact",
    ],
    "architecture": [
        "summary before details", "table", "modular",
    ],
    "explanation": [
        "summary before details", "table", "evidence",
    ],
    "configuration": [
        "concise", "modular", "evidence",
    ],
    "documentation": [
        "summary before details", "table", "concise",
    ],
    "review": [
        "summary before details", "evidence", "table",
    ],
}

# Bonus per affinity match (capped at max 2 matches → 0.4 max)
AFFINITY_BONUS = 0.2


def classify_task(prompt: str) -> str:
    """Classify a prompt into a task type. Returns the best match or 'general'."""
    text = prompt.lower()
    scores: dict[str, int] = {}
    for task_type, keywords in TASK_PATTERNS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[task_type] = score
    if not scores:
        return "general"
    return max(scores, key=scores.get)  # type: ignore[arg-type]


def task_affinity_bonus(task_type: str, pref_description: str) -> float:
    """Return a ranking bonus if this preference is useful for the detected task type."""
    if task_type == "general":
        return 0.0
    affinity_tags = TASK_AFFINITY.get(task_type, [])
    desc = pref_description.lower()
    matches = sum(1 for tag in affinity_tags if tag in desc)
    return min(matches * AFFINITY_BONUS, 0.4)
