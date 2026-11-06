"""Rule-based requirement extraction from a pasted job description.

The text is untrusted data. It is only split into lines and pattern-matched here; nothing in it is
followed as an instruction, and nothing is sent anywhere. Every explicit requirement keeps the
line it came from (`quote`) so the learner can check it. "Inferred" suggestions come from the
career's own profile, are labelled as such, and are never presented as the employer's words.

Rules:
- Section headings (Requirements, Preferred, Responsibilities, ...) set the category of the
  bullet points and sentences under them.
- Any line stating years of experience is an experience requirement.
- Tools and technologies are recognised from the career's tool list and a small list of common
  ones; competencies from a short keyword list. Each keeps its supporting line.
- Requirements are mapped to the career's skills by the words they share (never across careers).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.careers import CATALOG
from app.careers.skills import career_skills

MAX_EXPLICIT = 40
MAX_TOOLS = 10
MAX_COMPETENCIES = 6
MAX_INFERRED = 3
MAX_TEXT = 300
MAX_QUOTE = 500

SECTIONS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "preferred_skill",
        re.compile(r"\b(preferred|nice[- ]to[- ]have|bonus|desired|desirable|a plus|pluses)\b", re.I),
    ),
    (
        "responsibility",
        re.compile(
            r"\b(responsibilit\w*|what you(?:'|’)?ll do|what you will do|duties|day[- ]to[- ]day|the role|in this role|you will)\b",
            re.I,
        ),
    ),
    (
        "required_skill",
        re.compile(
            r"\b(requirements?|required|qualifications?|must[- ]haves?|what you(?:'|’)?ll need|what we(?:'|’)?re looking for|"
            r"who you are|about you|skills|you have|you bring|minimum)\b",
            re.I,
        ),
    ),
)
BULLET = re.compile(r"^\s*(?:[-*•·▪◦‣–—]|\d{1,2}[.)])\s+")
YEARS = re.compile(r"\b\d+\s*\+?\s*(?:-|to|–)?\s*\d*\s*\+?\s*years?\b", re.I)
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")

COMMON_TOOLS = (
    "Java",
    "Python",
    "JavaScript",
    "TypeScript",
    "SQL",
    "Go",
    "C++",
    "C#",
    "Kotlin",
    "Swift",
    "Ruby",
    "PHP",
    "React",
    "Angular",
    "Vue",
    "Node.js",
    "Spring",
    "Django",
    "Flask",
    "AWS",
    "Azure",
    "GCP",
    "Docker",
    "Kubernetes",
    "Terraform",
    "Git",
    "Linux",
    "PostgreSQL",
    "MySQL",
    "MongoDB",
    "Redis",
    "Kafka",
    "REST",
    "GraphQL",
    "Excel",
    "Salesforce",
    "Jira",
    "Tableau",
    "Power BI",
    "SAP",
    "QuickBooks",
    "Epic",
    "Cerner",
    "Figma",
    "Photoshop",
    "AutoCAD",
)
COMPETENCIES: dict[str, re.Pattern[str]] = {
    "Communication": re.compile(r"\b(communicat\w*|verbal|written|present\w*|explain\w*)\b", re.I),
    "Teamwork": re.compile(r"\b(team\w*|collaborat\w*|cross[- ]functional)\b", re.I),
    "Leadership": re.compile(r"\b(lead\w*|mentor\w*|supervis\w*|coach\w*)\b", re.I),
    "Problem solving": re.compile(
        r"\b(problem[- ]solv\w*|troubleshoot\w*|analytical|critical thinking)\b", re.I
    ),
    "Working under pressure": re.compile(
        r"\b(fast[- ]paced|under pressure|prioriti[sz]\w*|multi[- ]?task\w*|deadlines?)\b", re.I
    ),
    "Attention to detail": re.compile(r"\b(attention to detail|detail[- ]oriented|accura\w*)\b", re.I),
    "Customer focus": re.compile(r"\b(customer\w*|patient[- ]cent\w*|client\w*|guest\w*)\b", re.I),
}
# Competencies that the career question bank practises (others stay unmapped, shown as gaps).
COMPETENCY_SKILL = {
    "Communication": "Working with people",
    "Teamwork": "Working with people",
    "Customer focus": "Working with people",
    "Leadership": "Leadership",
    "Problem solving": "Judgment under pressure",
    "Working under pressure": "Judgment under pressure",
}
_STOP = set(
    [
        "and",
        "or",
        "the",
        "a",
        "an",
        "of",
        "to",
        "in",
        "with",
        "for",
        "on",
        "at",
        "by",
        "as",
        "from",
        "your",
        "our",
        "you",
        "we",
        "be",
        "is",
        "are",
        "will",
    ]
)


@dataclass
class Extracted:
    category: str
    text: str
    origin: str  # explicit | inferred
    quote: str | None
    skills: list[str] = field(default_factory=list)


def _clean(line: str) -> str:
    return re.sub(r"\s+", " ", BULLET.sub("", line)).strip(" ;,")


def _short(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _heading(line: str) -> str | None:
    """The section a heading line starts, if it is one."""
    s = line.strip().strip("#*_ ").rstrip(":")
    if not s or BULLET.match(line) or len(s) > 70 or (s.endswith(".") and len(s.split()) > 6):
        return None
    if not (line.strip().endswith(":") or len(s.split()) <= 6 or s.isupper()):
        return None
    for category, pattern in SECTIONS:
        if pattern.search(s):
            return category
    return "other" if line.strip().endswith(":") else None


def _words(s: str) -> list[str]:
    return [w for w in re.findall(r"[a-z]+", s.lower()) if w not in _STOP and len(w) > 2]


def map_skills(text: str, track: str) -> list[str]:
    """Career skills a requirement's text names (by shared words), plus mapped competencies."""
    lowered = text.lower()
    found: list[str] = []
    for skill in career_skills(track):
        words = _words(skill)
        if not words or skill in COMPETENCY_SKILL.values():
            continue
        hits = sum(w[:5] in lowered for w in words)
        if hits >= (len(words) if len(words) <= 2 else (len(words) + 1) // 2):
            found.append(skill)
    for name, pattern in COMPETENCIES.items():
        mapped = COMPETENCY_SKILL.get(name)
        if mapped and mapped in career_skills(track) and pattern.search(text) and mapped not in found:
            found.append(mapped)
    return found


def extract(description: str, track: str) -> list[Extracted]:
    profile = CATALOG[track]
    items: list[Extracted] = []
    seen: set[str] = set()
    section: str | None = None

    def add(category: str, text: str, quote: str) -> None:
        key = text.lower()
        if key in seen or len(text) < 3:
            return
        seen.add(key)
        items.append(
            Extracted(
                category,
                _short(text, MAX_TEXT),
                "explicit",
                _short(quote.strip(), MAX_QUOTE),
                map_skills(text, track),
            )
        )

    had_bullets = False  # a section's bullet list, then a blank line, then prose: the section is over
    gap = False
    for raw in description.splitlines():
        if not raw.strip():
            gap = True
            continue
        head = _heading(raw)
        if head is not None:
            section = None if head == "other" else head
            had_bullets = gap = False
            continue
        if section is not None and had_bullets and gap and not BULLET.match(raw):
            section = None
        gap = False
        had_bullets = had_bullets or bool(BULLET.match(raw))
        if len([i for i in items if i.origin == "explicit"]) >= MAX_EXPLICIT:
            break
        bullet = bool(BULLET.match(raw))
        parts = [raw] if bullet else [p for p in SENTENCE.split(raw.strip()) if p.strip()]
        for part in parts:
            text = _clean(part)
            if not text:
                continue
            if YEARS.search(text):
                add("experience", text, raw)
            elif section is not None:
                add(section, text, raw)

    lines = [ln for ln in description.splitlines() if ln.strip()]
    tools = [*profile.tools, *COMMON_TOOLS]
    n_tools = 0
    for tool in dict.fromkeys(tools):
        if n_tools >= MAX_TOOLS:
            break
        pattern = re.compile(rf"(?<![\w+#.]){re.escape(tool)}(?![\w+#])", 0 if tool in COMMON_TOOLS else re.I)
        line = next((ln for ln in lines if pattern.search(ln)), None)
        if line is not None and tool.lower() not in seen:
            seen.add(tool.lower())
            items.append(
                Extracted("tool", tool, "explicit", _short(line.strip(), MAX_QUOTE), map_skills(tool, track))
            )
            n_tools += 1
    n_comp = 0
    for name, pattern in COMPETENCIES.items():
        if n_comp >= MAX_COMPETENCIES:
            break
        line = next((ln for ln in lines if pattern.search(ln)), None)
        if line is not None:
            mapped = COMPETENCY_SKILL.get(name)
            skills = [mapped] if mapped and mapped in career_skills(track) else []
            items.append(Extracted("competency", name, "explicit", _short(line.strip(), MAX_QUOTE), skills))
            n_comp += 1

    covered = {s for i in items for s in i.skills}
    for skill in [s for s in profile.skills if s not in covered][:MAX_INFERRED]:
        items.append(
            Extracted(
                "required_skill",
                f"{skill[:1].upper()}{skill[1:]}",
                "inferred",
                None,
                [skill],
            )
        )
    return items
