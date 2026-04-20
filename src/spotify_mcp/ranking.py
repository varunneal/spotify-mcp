"""Pure ranking functions for SpotifySmartPlay.

No spotipy imports; testable in isolation. The scoring breakdown is
deliberately transparent so the rationale string can be assembled by
format_rationale.
"""
import re
from typing import Optional, List, Dict, Set, Tuple

STOPWORDS = frozenset({
    "a", "an", "the", "for", "with", "and", "of", "to",
    "some", "my", "me", "please", "i", "it", "on", "in",
})


def tokenize(text: str) -> List[str]:
    cleaned = re.sub(r"[^\w\s]", " ", (text or "").lower())
    return [t for t in cleaned.split() if t and t not in STOPWORDS]


def name_overlap(query_tokens: Set[str], candidate_name: str) -> float:
    cand = set(tokenize(candidate_name))
    if not query_tokens:
        return 0.0
    return len(query_tokens & cand) / len(query_tokens)


def prefer_bonus(candidate_type: str, prefer: Optional[str]) -> float:
    return 0.3 if prefer and candidate_type == prefer else 0.0


def curation_bonus(candidate: Dict) -> float:
    """Playlist-only signal: Spotify-owned editorial + reasonable track count."""
    score = 0.0
    owner_id = (candidate.get("owner_id") or "").lower()
    owner_name = (candidate.get("owner") or "").lower()
    if owner_id == "spotify" or owner_name == "spotify":
        score += 0.4
    total = candidate.get("total_tracks")
    if isinstance(total, int):
        if 30 <= total <= 1000:
            score += 0.2
        elif total < 10:
            score -= 0.3
        elif total > 2000:
            score -= 0.2
    return score


def taste_bonus(candidate: Dict, candidate_type: str, top_artist_ids: Set[str]) -> float:
    if not top_artist_ids:
        return 0.0
    if candidate_type in ("track", "album"):
        ids = candidate.get("_artist_ids") or set()
        if isinstance(ids, (list, tuple)):
            ids = set(ids)
        return 0.5 if ids & top_artist_ids else 0.0
    return 0.0


def score_candidate(candidate: Dict, candidate_type: str, query_tokens: Set[str],
                    top_artist_ids: Set[str], prefer: Optional[str]) -> Tuple[float, Dict[str, float]]:
    breakdown = {
        "name_overlap": name_overlap(query_tokens, candidate.get("name", "")),
        "prefer": prefer_bonus(candidate_type, prefer),
        "curation": curation_bonus(candidate) if candidate_type == "playlist" else 0.0,
        "taste": taste_bonus(candidate, candidate_type, top_artist_ids),
    }
    return sum(breakdown.values()), breakdown


def rank_candidates(candidates: List[Tuple[Dict, str]], query: str,
                    top_artist_ids: Set[str], prefer: Optional[str]) -> List[Dict]:
    q_tokens = set(tokenize(query))
    scored: List[Dict] = []
    for candidate, ctype in candidates:
        total, breakdown = score_candidate(candidate, ctype, q_tokens, top_artist_ids, prefer)
        scored.append({
            "candidate": candidate,
            "type": ctype,
            "score": total,
            "breakdown": breakdown,
        })
    scored.sort(key=lambda s: s["score"], reverse=True)
    return scored


def format_rationale(scored: Dict) -> str:
    bd = scored["breakdown"]
    parts = [f"{k} {v:+.2f}" for k, v in bd.items() if v]
    body = " ".join(parts) if parts else "no bonuses"
    return f"{body} = {scored['score']:.2f}"
