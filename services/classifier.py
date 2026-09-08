import re
from models import ReviewComment, CommentCategory


KEYWORDS = {
    CommentCategory.elogio: [
        r"\bótimo\b", r"\bexcelente\b", r"\bparabéns\b", r"\bbom trabalho\b",
        r"\bgreat\b", r"\bnice\b", r"\bwell done\b", r"\bawesome\b",
        r"\bthanks?\b", r"\bthank you\b", r"\bperfect\b", r"\blooks? good\b",
        r"\blgtm\b", r"\bapproved?\b",
    ],
    CommentCategory.rejeicao: [
        r"\breject\b", r"\bclosing\b", r"\bnão aceito\b", r"\bnão aprovado\b",
        r"\bwon'?t merge\b", r"\bout of scope\b", r"\bduplicate\b",
        r"\binvalid\b", r"\bfora do escopo\b",
    ],
    CommentCategory.correcao_tecnica: [
        r"\bbug\b", r"\berro\b", r"\berror\b", r"\bfix\b", r"\bcorri[gj]\b",
        r"\brefactor\b", r"\bperformance\b", r"\bvazamento\b", r"\bleak\b",
        r"\bsecurity\b", r"\bsegurança\b", r"\bnull\b", r"\bundefined\b",
        r"\bexception\b", r"\btype hint\b", r"\btest\b", r"\bteste\b",
        r"\bcomplexidade\b", r"\bO\(n\)", r"\balgorithm\b",
    ],
    CommentCategory.explicacao_didatica: [
        r"\bexplico\b", r"\bexplain\b", r"\bpor que\b", r"\bwhy\b",
        r"\bporque\b", r"\bconsidere\b", r"\bconsider\b", r"\bsugest\b",
        r"\bsuger\b", r"\brecomend\b", r"\brecomen\b", r"\bdocument\b",
        r"\blegibilidade\b", r"\breadability\b", r"\bboa prática\b",
        r"\bbest practice\b", r"\bpadrão\b", r"\bpattern\b", r"\bconvençã\b",
    ],
}


def auto_categorize(comment: ReviewComment) -> CommentCategory:
    text = comment.body.lower()

    scores: dict[CommentCategory, int] = {cat: 0 for cat in CommentCategory}

    for category, patterns in KEYWORDS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                scores[category] += 1

    best = max(scores, key=lambda c: scores[c])
    if scores[best] == 0:
        return CommentCategory.neutro

    return best


def apply_auto_categorization(comments: list[ReviewComment]) -> list[ReviewComment]:
    for comment in comments:
        if comment.category is None:
            comment.category = auto_categorize(comment)
    return comments
