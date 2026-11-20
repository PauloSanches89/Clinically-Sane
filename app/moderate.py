"""Note check without a language model. Queue numbers are never blocked here."""

from __future__ import annotations

import re

PHONE = re.compile(r"(?:\+27|27|0)\s*[1-8](?:[\s\-]*\d){8}\b")
SA_ID = re.compile(r"\b\d{13}\b")
THREAT = re.compile(
    r"\b(?:kill(?:s|ed|ing)?|murder(?:s|ed|ing)?|shoot(?:s|ing)?|shot|"
    r"stab(?:s|bed|bing)?|bomb(?:s|ed|ing)?|assault(?:s|ed|ing)?|rape[sd]?|raping)\b",
    re.IGNORECASE,
)
HARM = re.compile(
    r"\b(?:hurt|harm|attack|beat|punch|strangle)\b(?:\s+\w+){0,4}\s+"
    r"\b(?:you|her|him|them|nurse|nurses|doctor|doctors|staff|sister|sisters)\b",
    re.IGNORECASE,
)
STAFF_TITLE = re.compile(
    r"\b(?:nurse|nurses|dr|doctor|doctors|sister|sisters|matron|prof|professor)\.?\s+"
    r"(?:(?:van|de|der|den|da|du|le|la)\s+)?"
    r"([A-Za-z][A-Za-z'\-]{1,})\b",
    re.IGNORECASE,
)
BLOCKED_WORDS = re.compile(
    r"\b(?:nigger|nigga|kaffir|kaffer|coolie|hotnot|boesman|spic|chink|paki|"
    r"wetback|raghead|faggot|fag|tranny|retard|retarded|"
    r"porn|porno|nude|naked|penis|vagina|dick|cock|pussy|boobs|tits|"
    r"blowjob|handjob|orgasm|horny|slut)\b",
    re.IGNORECASE,
)
STAFF_STOP = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "on", "at", "in", "to", "of", "for", "from", "with", "and", "or",
    "today", "working", "work", "works", "worked", "only", "one", "two",
    "three", "four", "five", "six", "few", "many", "some", "all", "most",
    "other", "more", "no", "not", "here", "there", "this", "that", "who",
    "very", "too", "long", "short", "rude", "slow", "busy", "available",
    "duty", "station", "room", "rooms", "open", "closed", "away", "sent",
    "said", "told", "asked", "help", "helped", "helping", "staff", "clinic",
    "queue", "line", "waiting", "wait", "seen", "seeing", "just", "still",
    "left", "came", "come", "coming", "went", "gone", "going", "our", "their",
    "my", "your", "his", "her", "its", "out", "off", "up", "down", "back",
    "late", "early", "absent", "present", "alone", "around", "about",
    "people", "person", "someone", "anybody", "everyone", "nobody",
    "did", "does", "do", "has", "have", "had", "will", "can", "could",
    "would", "should", "please", "thanks", "thank",
}


def review_note(note: str) -> tuple[str | None, str]:
    """Return the note to store and a status of none, kept, or rejected."""
    text = " ".join((note or "").split())
    if not text:
        return None, "none"
    if _inappropriate(text):
        return None, "rejected"
    return text[:200], "kept"


def _inappropriate(text: str) -> bool:
    if PHONE.search(text) or SA_ID.search(text):
        return True
    if BLOCKED_WORDS.search(text) or HARM.search(text):
        return True
    if _named_staff(text):
        return True
    for match in THREAT.finditer(text):
        if match.group(0).lower() == "killing" and re.match(r"\s+(?:me|us)\b", text[match.end():], re.I):
            continue
        return True
    return False


def _named_staff(text: str) -> bool:
    for match in STAFF_TITLE.finditer(text):
        if match.group(1).lower() not in STAFF_STOP:
            return True
    return False
