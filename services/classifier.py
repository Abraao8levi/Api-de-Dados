import re
from models import ReviewComment, CommentCategory


PATTERNS: dict[CommentCategory, list[re.Pattern]] = {
    CommentCategory.rejeicao: [
        re.compile(p, re.IGNORECASE) for p in [
            r"\breject\w*", r"\bclos(e|ed|ing)\b", r"\bfech(ar|ado|ando)\b",
            r"\bnão aceit\w*", r"\bnão aprovad\w*", r"\bwon'?t merge\b",
            r"\bout of scope\b", r"\bduplicate\b", r"\binvalid\w*",
            r"\bfora do escopo\b", r"\bdescontinuad\w*",
        ]
    ],
    CommentCategory.correcao_tecnica: [
        re.compile(p, re.IGNORECASE) for p in [
            r"\bbug\b", r"\berro\w*", r"\berror\w*", r"\bfix\w*", r"\bcorri[gj]\w*",
            r"\brefactor\w*", r"\bperformance\b", r"\bvazamento\w*", r"\bleak\w*",
            r"\bsecurity\b", r"\bsegurança\b", r"\bnull\b", r"\bundefined\b",
            r"\bexception\b", r"\btype hint\w*", r"\bteste?s?\b", r"\bcomplexidade\b",
            r"\bO\([1nlog\^]+\)", r"\balgorithm\w*",
        ]
    ],
    CommentCategory.explicacao_didatica: [
        re.compile(p, re.IGNORECASE) for p in [
            r"\bexpli[ck]\w*", r"\bexplain\w*", r"\bpor que\b", r"\bwhy\b",
            r"\bporque\b", r"\bconsidere\b", r"\bconsider\w*", r"\bsugest\w*",
            r"\bsugir\w*", r"\brecomend\w*", r"\bdocument\w*", r"\blegibilidade\b",
            r"\breadability\b", r"\bboa prática\b", r"\bbest practice\b",
            r"\bpadr[ãõ]\w*", r"\bpatterns?\b", r"\bconvenç[ãõ]\w*",
        ]
    ],
    CommentCategory.elogio: [
        re.compile(p, re.IGNORECASE) for p in [
            r"\bótimo\b", r"\bexcelente\b", r"\bparabéns\b", r"\bbom trabalho\b",
            r"\bgreat\b", r"\bnice\b", r"\bwell done\b", r"\bawesome\b",
            r"\bthanks?\b", r"\bthank you\b", r"\bperfect\b", r"\blooks? good\b",
            r"\blgtm\b", r"\bapproved?\b",
        ]
    ],
}


def auto_categorize(comment: ReviewComment) -> CommentCategory:
    text = comment.body.lower()
    scores: dict[CommentCategory, int] = {cat: 0 for cat in CommentCategory}

    for category, compiled_patterns in PATTERNS.items():
        for pattern in compiled_patterns:
            if pattern.search(text):
                scores[category] += 1

    if scores[CommentCategory.rejeicao] > 0 and scores[CommentCategory.elogio] > 0:
        scores[CommentCategory.elogio] = 0

    best = max(scores, key=lambda c: scores[c])
    if scores[best] == 0:
        return CommentCategory.neutro

    return best


def apply_auto_categorization(comments: list[ReviewComment]) -> list[ReviewComment]:
    for comment in comments:
        if comment.category is None:
            comment.category = auto_categorize(comment)
    return comments
