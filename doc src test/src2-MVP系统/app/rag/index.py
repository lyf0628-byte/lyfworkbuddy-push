"""混合检索核心：标题感知切片 + BM25 + 向量余弦 + RRF 融合。

刻意做成"零第三方依赖"：只用标准库。
设计取舍：
- 中文没有空格，用 bigram 分词；
- 没有 embedding API 时，用特征哈希造稠密向量（hashing trick）；
- 融合用 RRF（Reciprocal Rank Fusion）。
"""
from __future__ import annotations

import heapq
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable

_CJK = r"\u4e00-\u9fff"
_ASCII_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_+\-\.]{0,}")
_CJK_RUN = re.compile(f"[{_CJK}]+")
_NUM = re.compile(r"\d+(?:\.\d+)?")

_STOPWORDS = {
    "的", "了", "是", "在", "和", "与", "及", "或", "有", "为", "对", "从", "到",
    "这", "那", "其", "之", "并", "等", "被", "把", "向", "按", "以", "于", "中",
    "我", "你", "他", "们", "个", "上", "下", "里", "就", "都", "也", "还", "要", "会",
}


def tokenize(text: str) -> list[str]:
    text = text.lower()
    tokens: list[str] = []
    for word in _ASCII_WORD.findall(text):
        if len(word) >= 2:
            tokens.append(word)
    tokens.extend(_NUM.findall(text))
    for run in _CJK_RUN.findall(text):
        chars = [c for c in run if c not in _STOPWORDS]
        if len(chars) == 1:
            tokens.append(chars[0])
            continue
        for i in range(len(chars) - 1):
            tokens.append(chars[i] + chars[i + 1])
    return tokens


# ---------------------------------------------------------------- 切片

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


def chunk_document(content: str, doc_title: str = "", chunk_size: int | None = None, overlap: int | None = None) -> list[dict[str, str]]:
    from ..config import settings

    chunk_size = chunk_size or settings.chunk_size
    overlap = overlap if overlap is not None else settings.chunk_overlap

    sections: list[tuple[str, list[str]]] = []
    heading_stack: list[tuple[int, str]] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer and any(line.strip() for line in buffer):
            path = " > ".join(h for _, h in heading_stack) or doc_title
            sections.append((path, buffer.copy()))
        buffer.clear()

    for line in content.splitlines():
        match = _HEADING.match(line)
        if match:
            flush()
            level = len(match.group(1))
            title = match.group(2).strip()
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, title))
            continue
        buffer.append(line)
    flush()

    chunks: list[dict[str, str]] = []
    for heading_path, lines in sections:
        text = "\n".join(lines).strip()
        if not text:
            continue
        if len(text) <= chunk_size:
            chunks.append({"heading": heading_path, "text": text})
            continue
        step = max(1, chunk_size - overlap)
        for start in range(0, len(text), step):
            piece = text[start:start + chunk_size].strip()
            if piece:
                chunks.append({"heading": heading_path, "text": piece})
            if start + chunk_size >= len(text):
                break
    return chunks


# ---------------------------------------------------------------- BM25

class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.docs = docs
        self.k1 = k1
        self.b = b
        self.n = len(docs)
        self.doc_len = [len(d) for d in docs]
        self.avg_len = (sum(self.doc_len) / self.n) if self.n else 0.0
        self.tf: list[Counter[str]] = [Counter(d) for d in docs]
        df: Counter[str] = Counter()
        for tf in self.tf:
            df.update(tf.keys())
        self.idf = {
            term: math.log(1 + (self.n - freq + 0.5) / (freq + 0.5))
            for term, freq in df.items()
        }

    def scores(self, query_tokens: Iterable[str]) -> list[float]:
        q = list(query_tokens)
        result = [0.0] * self.n
        for i in range(self.n):
            tf = self.tf[i]
            dl = self.doc_len[i] or 1
            score = 0.0
            for term in q:
                freq = tf.get(term)
                if not freq:
                    continue
                idf = self.idf.get(term, 0.0)
                denom = freq + self.k1 * (1 - self.b + self.b * dl / (self.avg_len or 1))
                score += idf * freq * (self.k1 + 1) / denom
            result[i] = score
        return result


# ---------------------------------------------------------------- 向量（特征哈希）

class HashEmbedder:
    def __init__(self, dim: int = 512) -> None:
        self.dim = dim

    def embed(self, tokens: list[str]) -> list[float]:
        vec = [0.0] * self.dim
        for token, count in Counter(tokens).items():
            h = 2166136261
            for ch in token:
                h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
            idx = h % self.dim
            vec[idx] += 1.0 + math.log(count)
        norm = math.sqrt(sum(v * v for v in vec))
        if norm:
            vec = [v / norm for v in vec]
        return vec


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


# ---------------------------------------------------------------- 索引与检索

@dataclass
class Chunk:
    doc_id: int
    doc_title: str
    filename: str
    version: str
    heading: str
    text: str
    tokens: list[str] = field(default_factory=list, repr=False)
    vector: list[float] = field(default_factory=list, repr=False)

    def citation(self, score: float) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id, "doc": self.filename, "doc_title": self.doc_title,
            "version": self.version, "heading": self.heading, "text": self.text,
            "score": round(score, 6),
        }


_QUERY_NOISE_CHARS = set("吗呢吧啊什怎多如何能否可以须要会能该把被很太都也还就请问一下")

_GENERIC_TOKENS = {
    "变更", "通知", "行程", "旅行", "公司", "员工", "制度", "规程", "标准", "规定",
    "流程", "情况", "需要", "提供", "申请", "进行", "以及", "其他", "相关",
}

# 行知旅行核心术语：命中即认为"这段规程在讲这件事"
_CORE_TERMS = {
    "遗漏", "回执", "确认", "口径", "审核门", "转人工", "四要素", "影响面", "主键",
    "版本", "升级", "超时", "红线", "退款", "改签", "赔偿", "留痕", "审计", "权限",
    "导游", "协调员", "服务商", "酒店", "车队", "旅客", "授权", "拍板", "试点", "覆盖率",
    "留存", "名单", "脱敏", "90", "天",
}

_QUERY_HINTS: list[tuple[tuple[str, ...], str]] = [
    (("遗漏率", "目标", "多少"), "通知遗漏率 14% 降到 2%"),
    (("耗时", "异常确认", "多久"), "异常确认耗时 80 分钟 降到 20 分钟"),
    (("审核门", "有几道", "哪几道"), "五道审核门 G1 G2 G3 G4 G5"),
    (("转人工", "四要素", "哪些"), "转人工四要素 触发原因 接手人 确认时间 业务编号 版本"),
    (("退款", "改签", "赔偿"), "不可逆动作 强制人工 红线 不自主执行"),
    (("回执", "口径", "完成"), "确认回执 发出 完成口径 已读 资源可用"),
    (("留存", "保留", "存储", "多久", "多长时间"), "90 天 留存 审计 安全主管 复核"),
    (("主键", "字段", "关联"), "团号 订单号 版本号 主键"),
    (("名单", "谁能看", "可见"), "旅客名单 最小可见 脱敏 授权"),
]

_OOS_TERMS = {
    "机票预订", "签证", "保险", "购物", "景点门票", "餐饮推荐", "娱乐",
    "代购", "礼品", "贷款", "投资",
}


def expand_query(query: str) -> str:
    extra: list[str] = []
    for keys, hint in _QUERY_HINTS:
        if any(k in query for k in keys):
            extra.append(hint)
    if not extra:
        return query
    return query + " " + " ".join(extra)


def is_out_of_scope(query: str) -> bool:
    return any(term in query for term in _OOS_TERMS)


def gate_tokens(query: str) -> list[str]:
    out: list[str] = []
    for tok in tokenize(query):
        if tok in _GENERIC_TOKENS:
            continue
        if any(ch in _QUERY_NOISE_CHARS for ch in tok):
            continue
        out.append(tok)
    return out


class PolicyIndex:
    def __init__(self, chunks: list[Chunk], top_k: int = 3, rrf_k: int = 60) -> None:
        self.chunks = chunks
        self.top_k = top_k
        self.rrf_k = rrf_k
        self.embedder = HashEmbedder()
        for chunk in self.chunks:
            chunk.tokens = tokenize(chunk.heading + "\n" + chunk.text)
            chunk.vector = self.embedder.embed(chunk.tokens)
        self.bm25 = BM25([c.tokens for c in self.chunks]) if self.chunks else None

    def bm25_ranking(self, query: str) -> list[tuple[int, float]]:
        if not self.bm25:
            return []
        scores = self.bm25.scores(tokenize(query))
        ranked = sorted(enumerate(scores), key=lambda kv: kv[1], reverse=True)
        return [(i, s) for i, s in ranked if s > 0]

    def vector_ranking(self, query: str) -> list[tuple[int, float]]:
        if not self.chunks:
            return []
        qv = self.embedder.embed(tokenize(query))
        scores = [(i, cosine(qv, c.vector)) for i, c in enumerate(self.chunks)]
        ranked = sorted(scores, key=lambda kv: kv[1], reverse=True)
        return [(i, s) for i, s in ranked if s > 0.01]

    def search(self, query: str, top_k: int | None = None) -> list[dict[str, Any]]:
        k = top_k or self.top_k
        if is_out_of_scope(query):
            return []
        expanded = expand_query(query)
        bm25_rank = self.bm25_ranking(expanded)
        vec_rank = self.vector_ranking(expanded)

        fused: dict[int, float] = {}
        for ranking in (bm25_rank, vec_rank):
            for rank, (idx, _score) in enumerate(ranking, start=1):
                fused[idx] = fused.get(idx, 0.0) + 1.0 / (self.rrf_k + rank)

        best = heapq.nlargest(k, fused.items(), key=lambda kv: kv[1]) if fused else []

        gate = gate_tokens(expanded)
        if not gate:
            gate = tokenize(expanded)
        gate_set = set(gate)
        hits: list[dict[str, Any]] = []
        for idx, score in best:
            chunk = self.chunks[idx]
            if not self._relevant(gate_set, set(chunk.tokens)):
                continue
            hits.append(chunk.citation(score))
        return hits

    @staticmethod
    def _relevant(query_tokens: set[str], chunk_tokens: set[str], min_ratio: float = 0.34) -> bool:
        if not query_tokens or not chunk_tokens:
            return False
        matched = query_tokens & chunk_tokens
        if not matched:
            return False
        ratio = len(matched) / len(query_tokens)
        if len(matched) >= 2 and ratio >= min_ratio:
            return True
        if matched & _CORE_TERMS:
            return True
        return len(matched) >= 1 and ratio >= 0.5


_CACHE: dict[tuple, PolicyIndex] = {}


def get_index(conn: Any, top_k: int | None = None, rrf_k: int | None = None) -> PolicyIndex:
    from ..config import settings

    docs = conn.execute(
        "SELECT id, filename, title, version, updated_at FROM policy_docs WHERE status = 'active' ORDER BY id"
    ).fetchall()
    signature = tuple((d["id"], d["updated_at"], d["version"]) for d in docs)
    cache_key = (signature, top_k, rrf_k)

    cached = _CACHE.get(cache_key)
    if cached is not None:
        return cached

    chunks: list[Chunk] = []
    for doc in docs:
        rows = conn.execute(
            "SELECT heading, text FROM policy_chunks WHERE doc_id = ? ORDER BY ord", (doc["id"],)
        ).fetchall()
        for row in rows:
            chunks.append(Chunk(
                doc_id=doc["id"], doc_title=doc["title"], filename=doc["filename"],
                version=doc["version"], heading=row["heading"], text=row["text"],
            ))

    index = PolicyIndex(chunks, top_k=top_k or settings.top_k, rrf_k=rrf_k or settings.rrf_k)
    _CACHE.clear()
    _CACHE[cache_key] = index
    return index
