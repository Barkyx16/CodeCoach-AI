"""Turn a job profile into 300 interview questions (100 easy, 100 medium, 100 hard).

Each question comes from a template written by hand for one kind of interview question
(knowledge, behavioral, situational, leadership, motivation) and is filled in with that job's
own skills, tools, situations, people and metrics. Each one carries:

- a rubric: what a strong answer covers, with the words that show a point was covered and advice
  for when it wasn't (used by the offline grader in app/careers/grading.py);
- an outline of a strong answer, shown after the learner answers;
- tips shown before answering.

Questions are generated, not stored. Generation is deterministic, and each id encodes the template
and the slots it used ("m-walk-3" = medium "walk me through" template, situation #3), so ids stay
stable even if templates are added or reordered.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from functools import lru_cache
from itertools import combinations

from app.careers import CATALOG
from app.careers.profiles import JobProfile
from app.content import state as content_state

PER_LEVEL = 100

# Patterns shared by the rubric and the grader (app/careers/grading.py). The grader matches them
# against the answer with apostrophes and filler sounds ("um", "uh") taken out, so a dictated
# answer and a typed one with the same words are matched alike (rubric v3).
NUMBER_WORDS = (
    "two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|"
    "seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|"
    "million|dozen|half"
)
# A number as digits or as speech-to-text writes it ("nine", "two hours", "one week").
NUMBER = rf"(?:\d|\b(?:{NUMBER_WORDS})\b|\bone (?:minute|hour|day|week|month|year|shift|night|percent)s?\b)"
PERCENT = rf"(?:\d+ ?%|\b(?:\d+|(?:{NUMBER_WORDS}|one)(?:[ -](?:{NUMBER_WORDS}|one))?) percent\b)"
# The action criterion (rubric v7; evals/protocol.json labeling.action_criterion): something the
# learner did, or took part in doing, told as done. The grader matches these against the answer
# with apostrophes and filler sounds taken out, so "I'd already called" reads "id already called".
#
# Who: "I", "we", "me" in a pair ("our physio and me"), "the two of us". A team action counts, so
# nobody has to claim team work as their own ("Makes your own responsibility clear" asks for their
# part separately). Someone else's action has no such subject and doesn't count.
# Done: a past form (any verb ending in -ed, or an irregular past form below), after "had" too
# ("I had already called"; not "if I had"). Present tense isn't read as done: "so I go in and
# check" can't be told apart from a habit ("I check every patient") by its words, and a habit
# stated in general isn't what happened. "Would", "didn't", "never", "was going to" and "planned
# to" put no past form straight after the subject, so they don't count.
# An act: thinking, feeling, wanting, trying and meeting a situation don't count (_NOT_ACTIONS), nor
# does "what I took from it" (the lesson).
# The words between the subject and the verb: an aside in commas ("I, as nurse in charge, ...") and
# up to two adverbs, except those of habit, frequency or a near miss (usually, nearly, barely).
# A passive counts when it says the learner did it ("was measured by me"); one that doesn't say
# who ("the team was called") doesn't.
#
# The irregular forms are the closed class of English irregular verbs that name an act, as past
# forms and past participles; verbs of perceiving, knowing or feeling (saw, knew, felt, thought)
# are left out on purpose.
_IRREGULAR_ACTIONS = (
    "went|told|gave|took(?!\\s+(?:away|from)\\b)|made|brought|sent|wrote|spoke|met|ran|rang|sat|stood|put|set|led|"
    "kept|found|held|drove|taught|began|paid|left|said|sought|caught|fed|built|spent|chose|broke|split|cut|shut|"
    "got|drew|hung|threw|wore|dealt|swept|struck|bought|sold|lent|let|lit|laid|rode|shook|sang|slid|sprang|stuck|"
    "swung|tore|woke|wound|bent|bound|blew|dug|fled|flew|fought|forgave|froze|hid|hit|knelt|quit|spread|withdrew|"
    "withheld|upheld|undertook|oversaw|rewrote|retook|rebuilt|reset|redid|came|read|"
    r"did(?!\s*(?:not|nt)\b)"
)
# Past participles that differ from the past form, for "had ..." and passives
_IRREGULAR_PARTICIPLES = (
    "taken|given|done|gone|written|spoken|drawn|driven|chosen|broken|begun|shown|hidden|ridden|shaken|torn|"
    "thrown|woken|worn|withdrawn|undertaken|overseen|rewritten|retaken|flown|forgiven|frozen|sung|rung|sprung|"
    "blown|redone|come"
)


def irregular_actions() -> str:
    """The irregular past-tense action verbs, as a regex alternation (the grader uses them too)."""
    return _IRREGULAR_ACTIONS


_NOT_ACTIONS = (
    "wanted|needed|hoped|worried|wondered|liked|loved|hated|seemed|appeared|realised|realized|learned|"
    "noticed|assumed|believed|expected|preferred|enjoyed|panicked|struggled|tried|considered|imagined|"
    "guessed|cared|feared|doubted|trusted|remembered|happened|mattered|belonged|wished|planned|intended|"
    "faced|experienced|encountered|witnessed|"
    r"failed|owed|deserved|lacked|depended|existed|used(?= to\b)"
)
_ACTION_VERB = rf"(?:(?:{_IRREGULAR_ACTIONS}|{_IRREGULAR_PARTICIPLES})\b|(?!(?:{_NOT_ACTIONS})\b)[a-z]+ed\b)"
_SUBJECT_ = r"(?<!if )\b(?:i|we|(?:and|&) me|the (?:two|three|four) of us|both of us)"
_ASIDE = r"(?:,\s[^,.!?]{1,40},)?\s"
_ADVERBS = (
    r"(?:(?:then|also|first|finally|immediately|personally|just|instead|actually|later|eventually|straight away|"
    r"right away|already|both|all|together|next|soon|then also|"
    r"(?!(?:usually|normally|generally|typically|nearly|hardly|barely|scarcely|rarely|really|only)\b)[a-z]+ly)\s+)"
    r"{0,2}"
)
# "I had already ...", "we'd ..." (after the apostrophe is removed: "wed", "id") + a past participle
_HAD = r"(?:(?:had|d)\s+" + _ADVERBS + ")?"
ACTION = (
    _SUBJECT_
    + _ASIDE
    + _ADVERBS
    + _HAD
    + _ACTION_VERB
    + r"|(?<!if )\b(?:id|wed)\s+"
    + _ADVERBS
    + _ACTION_VERB
)
# A second action sharing that subject in the same sentence: "I listed the tasks, gave the insulin
# first and booked the teaching", "... plus practised it". Matches once per such sentence, so
# together with ACTION it shows two actions; a verb counts only after an action of the learner's in
# its own sentence ("her pressure dropped, and stabilized" doesn't).
_JOIN = r"(?:[,;] (?:and |then |and then |plus |as well as )?| and (?:then |also )?| plus | then )"
JOINED_ACTION = rf"(?:{ACTION})[^.!?]*?{_JOIN}{_ADVERBS}{_ACTION_VERB}"
# "I made sure to count her breaths, listen to her chest and record it": the acts after "made sure
# to" are base forms, so a comma list of them counts as the second action (once per sentence).
LISTED_ACTIONS = (
    rf"(?:{_SUBJECT_}){_ASIDE}{_ADVERBS}(?:made sure|took care|went on|set about|proceeded)\s+to\s+[a-z]+"
    r"[^.!?]*?, (?:and |plus |then )?[a-z]+"
)
# A passive that says the learner did it: "the bloods were taken by me", "an alert was stuck by me".
BY_ME = rf"\b(?:was|were)\s+{_ADVERBS}{_ACTION_VERB}[^.!?,;]{{0,60}}?\bby (?:me|myself|us|the two of us)\b"
LEVELS = ("easy", "medium", "hard")


@dataclass(frozen=True)
class RubricPoint:
    label: str  # what a strong answer does, e.g. "Shares a measurable result"
    patterns: tuple[str, ...]  # regexes; any one matching (case-insensitive) counts as covered
    advice: str  # what to add when it's missing
    min_hits: int = 1  # how many matches are needed (e.g. several "I ..." action statements)


@dataclass(frozen=True)
class Question:
    id: str
    track: str
    difficulty: str
    kind: str
    title: str
    prompt: str
    tags: tuple[str, ...]
    rubric: tuple[RubricPoint, ...]
    outline: tuple[str, ...]
    tips: tuple[str, ...]
    # 1 is the generated original; each published correction adds one (app/content).
    version: int = 1


# ----------------------------------------------------------------------------------------------
# Rubric building blocks
# ----------------------------------------------------------------------------------------------

_STOP = frozenset(
    [
        "a",
        "an",
        "and",
        "the",
        "of",
        "to",
        "in",
        "on",
        "for",
        "with",
        "your",
        "their",
        "at",
        "by",
        "or",
        "as",
        "from",
        "into",
    ]
)


def words_of(*phrases: str) -> tuple[str, ...]:
    """Significant words of job phrases, as regexes: 'patient assessment' -> patient, assess."""
    out: list[str] = []
    for phrase in phrases:
        for w in re.findall(r"[a-z0-9/+.#-]+", phrase.lower()):
            w = w.strip(".-")
            if len(w) >= 3 and w not in _STOP:
                # Match the word start so "assessment" also matches "assess", "assessing".
                out.append(r"\b" + re.escape(w[:7] if len(w) > 8 else w))
    return tuple(dict.fromkeys(out))


STAR = (
    RubricPoint(
        "Sets the scene: where you were and what was at stake",
        (
            r"\bwhen\b",
            r"situation",
            r"\bat my\b",
            r"\bwhile i\b",
            r"\bwe had\b",
            r"\bat the time\b",
            r"\bduring\b",
            r"\blast (year|month|summer|semester)\b",
            r"\bin my (previous|last|current)\b",
            r"\bonce\b",
            r"\bone time\b",
        ),
        "Open with one or two sentences of context: where you were, what was happening and why it mattered.",
    ),
    RubricPoint(
        "Makes your own responsibility clear",
        (
            r"\bmy (role|job|responsibilit|goal|task)",
            r"\bi was (responsible|in charge|asked|tasked)",
            r"\bi needed to\b",
            r"\bi had to\b",
            r"\bit was up to me\b",
            r"\bmy part\b",
        ),
        "Say what you personally were responsible for, not just what the team did.",
    ),
    RubricPoint(
        "Describes specific actions you took",
        (ACTION, JOINED_ACTION, LISTED_ACTIONS, BY_ME),
        "Walk through two or three concrete things you did, alone or with the team, told as what happened "
        "(“I checked …, then we …”).",
        min_hits=2,
    ),
    RubricPoint(
        "Shares a result, ideally with a number",
        (
            NUMBER,
            r"\bresult",
            r"\boutcome",
            r"\bimproved\b",
            r"\breduced\b",
            r"\bincreased\b",
            r"\bsaved\b",
            r"\bled to\b",
            r"\bended up\b",
            r"\bin the end\b",
            r"\bsuccess",
            r"\bresolved\b",
        ),
        "Finish with what happened because of your actions. A number (time saved, % improved, score) makes it stick.",
    ),
    RubricPoint(
        "Reflects on what you learned",
        (
            r"\blearn",
            r"\bnext time\b",
            r"\bdo differently\b",
            r"\btaught me\b",
            r"\bsince then\b",
            r"\bnow i\b",
            r"\bgoing forward\b",
            r"\bi realized\b",
            r"\btakeaway\b",
        ),
        "Close with one sentence on what you learned or what you'd do differently.",
    ),
)

ASSESS = RubricPoint(
    "Gathers information before acting",
    (
        r"\bassess",
        r"\bcheck",
        r"\bgather",
        r"\bfind out\b",
        r"\bunderstand",
        r"\bask(ing)?\b",
        r"\blook (at|into)\b",
        r"\bverify",
        r"\bconfirm",
        r"\bclarif",
        r"\binvestigat",
        r"\bfirst\b",
    ),
    "Start by saying how you'd get the facts: what you'd check, who you'd ask, what you'd confirm.",
)
PRIORITIZE = RubricPoint(
    "Puts the most urgent risk or safety first",
    (
        r"\bsafe",
        r"\burgent",
        r"\bpriorit",
        r"\brisk",
        r"\bimmediately\b",
        r"\bright away\b",
        r"\bmost important\b",
        r"\bcritical\b",
        r"\bfirst\b",
        r"\bbefore anything\b",
    ),
    "Say what you'd handle first and why. Interviewers want to see you protect people and the business from the biggest risk.",
)
FOLLOW_UP = RubricPoint(
    "Follows up, documents and prevents a repeat",
    (
        r"\bfollow(ed|ing)?[ -]up\b",
        r"\bdocument",
        r"\brecord",
        r"\bwrite (it )?up\b",
        r"\breport",
        r"\bprevent",
        r"\bnext time\b",
        r"\breview",
        r"\bdebrief",
        r"\bafterwards?\b",
        r"\blessons?\b",
        r"\broot cause\b",
    ),
    "End with what you'd do afterwards: write it up, check back, and change something so it doesn't happen again.",
)
WHY = RubricPoint(
    "Explains why it matters",
    (
        r"\bbecause\b",
        r"\bso that\b",
        r"\bmatters?\b",
        r"\bimportant\b",
        r"\bimpact",
        r"\baffects?\b",
        r"\bwhich means\b",
        r"\botherwise\b",
        r"\bthe reason\b",
    ),
    "Add a sentence on why this matters: who is affected and what goes wrong without it.",
)
EXAMPLE = RubricPoint(
    "Backs it up with a concrete example",
    (
        r"\bfor example\b",
        r"\bfor instance\b",
        r"\bsuch as\b",
        r"\blike when\b",
        r"\be\.g\b",
        r"\bone time\b",
        r"\bonce\b",
        r"\bi remember\b",
        r"\bin my\b",
    ),
    "Give one short, real example. It's what makes an answer believable.",
)
STEPS = RubricPoint(
    "Lays out clear steps or habits",
    (
        r"\bfirst\b",
        r"\bthen\b",
        r"\bnext\b",
        r"\bfinally\b",
        r"\bstep",
        r"\bmake sure\b",
        r"\balways\b",
        r"\bcheck",
        r"\bhabit",
        r"\bprocess\b",
        r"\broutine\b",
    ),
    "Give an order: first …, then …, finally …. Structure shows you'd do it reliably.",
)
TRADE_OFF = RubricPoint(
    "Names the trade-off and how you'd decide",
    (
        r"\btrade[- ]?off\b",
        r"\bbalance\b",
        r"\bdepends\b",
        r"\bweigh",
        r"\bon the other hand\b",
        r"\bbut\b",
        r"\bpriorit",
        r"\bcompromise\b",
        r"\bdecid",
    ),
    "Say what you'd give up and why. Strong answers admit there's a cost and explain the call.",
)
MEASURE = RubricPoint(
    "Says how you'd measure success",
    (
        r"\bmeasur",
        r"\btrack",
        r"\bmetric",
        r"\bkpi\b",
        r"\btarget\b",
        r"\bgoal\b",
        r"\bbaseline\b",
        PERCENT,
        r"\bweekly\b",
        r"\bdashboard\b",
        r"\bdata\b",
    ),
    "Say what number you'd watch, where it starts and what “better” looks like by when.",
)
ETHICS = RubricPoint(
    "Holds to standards and is honest",
    (
        r"\bhonest",
        r"\btranspar",
        r"\bstandard",
        r"\bpolicy\b",
        r"\bethic",
        r"\bthe right thing\b",
        r"\bown(ed)? up\b",
        r"\badmit",
        r"\bresponsib",
        r"\bwouldn'?t\b",
        r"\brefuse",
        r"\bsafe",
        r"\bcompliance\b",
        r"\brules?\b",
    ),
    "Make your line clear: you'd stay honest and within the rules, even when it's inconvenient.",
)
RESPECT = RubricPoint(
    "Listens and stays respectful",
    (
        r"\blisten",
        r"\bunderstand",
        r"\btheir (view|perspective|point|concern)",
        r"\bempath",
        r"\bcalm",
        r"\brespect",
        r"\backnowledg",
        r"\bhear (them|him|her) out\b",
        r"\bprivately\b",
    ),
    "Show you'd listen first and keep it respectful, even if you disagree.",
)
GROWTH = RubricPoint(
    "Shows a plan to learn or improve",
    (
        r"\blearn",
        r"\bpractice",
        r"\bcourse",
        r"\btraining",
        r"\bmentor",
        r"\bfeedback",
        r"\bread",
        r"\bshadow",
        r"\bcertif",
        r"\bstud(y|ied)",
        r"\bimprove",
    ),
    "Mention a concrete way you'd learn: practice, a course, a mentor, feedback.",
)
MOTIVATION = RubricPoint(
    "Gives a genuine, specific reason",
    (
        r"\bbecause\b",
        r"\bi (love|enjoy|care|like|want)\b",
        r"\bpassion",
        r"\bexcit",
        r"\bmotivat",
        r"\bwhy i\b",
        r"\bdrawn\b",
        r"\binterest",
    ),
    "Give a real reason in your own words. Specific beats generic every time.",
)
STRENGTH = RubricPoint(
    "Connects your strengths to the job",
    (
        r"\bstrength",
        r"\bgood at\b",
        r"\bskill",
        r"\bexperience",
        r"\bi bring\b",
        r"\bi can\b",
        r"\bmy background\b",
        r"\bi have\b",
    ),
    "Link what you're good at to what this job needs.",
)


def communicate(p: JobProfile, people: str | None = None) -> RubricPoint:
    who = words_of(people) if people else words_of(*p.people)
    return RubricPoint(
        f"Communicates with {people or 'the right people'}",
        (
            r"\btell",
            r"\binform",
            r"\bupdate",
            r"\bcommunicat",
            r"\bexplain",
            r"\bcall",
            r"\btalk",
            r"\blet (them|him|her)",
            r"\bescalat",
            r"\bkeep .* (informed|posted|updated)",
            *who,
        ),
        f"Say who you'd talk to ({people or ', '.join(p.people[:2])}), what you'd tell them and when.",
    )


def uses_job(p: JobProfile, *phrases: str, label: str | None = None) -> RubricPoint:
    vocab = phrases or (*p.skills, *p.tools)
    return RubricPoint(
        label or "Uses the specifics of the job",
        words_of(*vocab),
        f"Name the real parts of the work ({', '.join(vocab[:3])}). Specific job language shows you know the role.",
    )


# ----------------------------------------------------------------------------------------------
# Templates
# ----------------------------------------------------------------------------------------------

Slots = dict[str, str]
Builder = Callable[[JobProfile, Slots], tuple[RubricPoint, ...]]


@dataclass(frozen=True)
class Template:
    key: str
    difficulty: str
    kind: str
    title: str
    prompt: str
    slots: Callable[[JobProfile], Iterator[tuple[str, Slots]]]
    rubric: Builder
    outline: tuple[str, ...]


def _skills(p: JobProfile, limit: int = 8) -> Iterator[tuple[str, Slots]]:
    for i, s in enumerate(p.skills[:limit]):
        yield str(i), {"skill": s}


def _tools(p: JobProfile) -> Iterator[tuple[str, Slots]]:
    for i, t in enumerate(p.tools[:5]):
        yield str(i), {"tool": t}


def _people(p: JobProfile) -> Iterator[tuple[str, Slots]]:
    for i, x in enumerate(p.people[:4]):
        yield str(i), {"people": x}


def _metrics(p: JobProfile) -> Iterator[tuple[str, Slots]]:
    for i, m in enumerate(p.metrics[:4]):
        yield str(i), {"metric": m}


def _situations(p: JobProfile, limit: int = 8) -> Iterator[tuple[str, Slots]]:
    for i, s in enumerate(p.situations[:limit]):
        yield str(i), {"situation": s}


def _skill_pairs(p: JobProfile) -> Iterator[tuple[str, Slots]]:
    for (i, a), (j, b) in combinations(list(enumerate(p.skills[:6])), 2):
        yield f"{i}-{j}", {"skill": a, "skill2": b}


def _situation_pairs(p: JobProfile) -> Iterator[tuple[str, Slots]]:
    for (i, a), (j, b) in combinations(list(enumerate(p.situations[:8])), 2):
        yield f"{i}-{j}", {"situation": a, "situation2": b}


def _situation_people(limit: int) -> Callable[[JobProfile], Iterator[tuple[str, Slots]]]:
    def gen(p: JobProfile) -> Iterator[tuple[str, Slots]]:
        for i, s in enumerate(p.situations[:limit]):
            for j, who in enumerate(p.people[:4]):
                yield f"{i}-{j}", {"situation": s, "people": who}

    return gen


def _people_skills(p: JobProfile) -> Iterator[tuple[str, Slots]]:
    for i, who in enumerate(p.people[:4]):
        for j, s in enumerate(p.skills[:4]):
            yield f"{i}-{j}", {"people": who, "skill": s}


def _general(
    prompts: tuple[tuple[str, str, str], ...],
) -> Callable[[JobProfile], Iterator[tuple[str, Slots]]]:
    def gen(p: JobProfile) -> Iterator[tuple[str, Slots]]:
        for i, (title, prompt, kind) in enumerate(prompts):
            yield str(i), {"_title": title, "_prompt": prompt, "_kind": kind}

    return gen


GENERAL_PROMPTS: tuple[tuple[str, str, str], ...] = (
    ("Why this job", "Why do you want to work as {a_role}?", "motivation"),
    (
        "Tell me about yourself",
        "Tell me about yourself and how your background connects to working as {a_role}.",
        "motivation",
    ),
    (
        "A day in the job",
        "What do you think a typical day looks like for {a_role}, and which part appeals to you most?",
        "motivation",
    ),
    (
        "Your strengths",
        "What strengths would you bring to this {role} role? Give an example of each.",
        "behavioral",
    ),
    ("A weakness", "What's a weakness you're working on, and what are you doing about it?", "behavioral"),
    ("Organizing your day", "How do you organize your day when you have more tasks than time?", "behavioral"),
    ("Learning fast", "Tell me about a time you had to learn something new quickly.", "behavioral"),
    (
        "Taking feedback",
        "Tell me about a time you got critical feedback. What did you do with it?",
        "behavioral",
    ),
    (
        "Where you're headed",
        "Where do you see yourself in three years, and how does this {role} job fit in?",
        "motivation",
    ),
    ("Your first 30 days", "If we hired you, what would you focus on in your first 30 days?", "motivation"),
    ("Staying current", "How do you keep your skills and knowledge current as {a_role}?", "knowledge"),
    (
        "Working on a team",
        "Tell me about a time you worked well as part of a team. What was your part?",
        "behavioral",
    ),
)


def _general_rubric(p: JobProfile, s: Slots) -> tuple[RubricPoint, ...]:
    if s["_kind"] == "motivation":
        return (MOTIVATION, STRENGTH, EXAMPLE, uses_job(p, label=f"Shows you understand the {p.role} role"))
    if s["_kind"] == "knowledge":
        return (GROWTH, STEPS, EXAMPLE, uses_job(p))
    return STAR


TEMPLATES: tuple[Template, ...] = (
    # ---------------------------------------------------------------- easy (fundamentals)
    Template(
        "e-good",
        "easy",
        "knowledge",
        "What good {skill} looks like",
        "What does good {skill} look like for {a_role}?",
        _skills,
        lambda p, s: (
            uses_job(p, s["skill"], label=f"Talks about {s['skill']} specifically"),
            WHY,
            EXAMPLE,
            STEPS,
        ),
        (
            "Define {skill} in one plain sentence.",
            "Describe two or three signs it's being done well.",
            "Say why it matters to {people_list}.",
            "Give a short example from work, school or volunteering.",
        ),
    ),
    Template(
        "e-steps",
        "easy",
        "knowledge",
        "Your approach to {skill}",
        "Walk me through how you approach {skill}, step by step.",
        _skills,
        lambda p, s: (
            STEPS,
            uses_job(p, s["skill"], *p.tools, label="Uses the right tools and terms"),
            WHY,
            FOLLOW_UP,
        ),
        (
            "Give the steps in order (first, then, finally).",
            "Name the tools you'd use ({tool_list}).",
            "Say how you check the result.",
            "Mention what you'd record or hand off afterwards.",
        ),
    ),
    Template(
        "e-time",
        "easy",
        "behavioral",
        "A time {skill} mattered",
        "Tell me about a time {skill} was an important part of your work, studies or volunteering.",
        _skills,
        lambda p, s: (*STAR[:4], uses_job(p, s["skill"], label=f"Shows {s['skill']} in action")),
        (
            "Situation: where you were and what was happening.",
            "Task: what you were responsible for.",
            "Action: two or three specific things you did involving {skill}.",
            "Result: what changed, with a number if you can.",
        ),
    ),
    Template(
        "e-mistake",
        "easy",
        "knowledge",
        "Common mistakes in {skill}",
        "What's a common mistake people new to the job make with {skill}, and how would you avoid it?",
        _skills,
        lambda p, s: (uses_job(p, s["skill"], label="Names a realistic mistake"), WHY, STEPS, GROWTH),
        (
            "Name one specific, realistic mistake.",
            "Explain what goes wrong because of it.",
            "Describe the habit or check that prevents it.",
            "Say how you'd keep improving.",
        ),
    ),
    Template(
        "e-explain",
        "easy",
        "knowledge",
        "Explaining {skill} simply",
        "How would you explain {skill} to someone who has never worked as {a_role}?",
        _skills,
        lambda p, s: (
            RubricPoint(
                "Uses plain, everyday language",
                (
                    r"\blike\b",
                    r"\bimagine\b",
                    r"\bthink of\b",
                    r"\bsimpl",
                    r"\bbasically\b",
                    r"\bin other words\b",
                    r"\bmeans\b",
                ),
                "Use an everyday comparison (“it's like …”) instead of jargon.",
            ),
            uses_job(p, s["skill"], label=f"Stays accurate about {s['skill']}"),
            WHY,
            EXAMPLE,
        ),
        (
            "Start with a one-sentence plain definition.",
            "Use an everyday comparison.",
            "Give a quick example from the job.",
            "Say why it matters to the people you serve.",
        ),
    ),
    Template(
        "e-accuracy",
        "easy",
        "knowledge",
        "Checking your {skill} work",
        "How do you check your own work when it comes to {skill}?",
        _skills,
        lambda p, s: (STEPS, uses_job(p, s["skill"], *p.tools), WHY, FOLLOW_UP),
        (
            "Describe the checks you run before calling it done.",
            "Name a tool or checklist ({tool_list}).",
            "Explain what a mistake would cost.",
            "Say what you do when you catch one.",
        ),
    ),
    Template(
        "e-learn",
        "easy",
        "knowledge",
        "Getting better at {skill}",
        "If you wanted to get noticeably better at {skill} in the next three months, what would you do?",
        _skills,
        lambda p, s: (GROWTH, MEASURE, STEPS, uses_job(p, s["skill"])),
        (
            "Pick one specific gap.",
            "Choose how you'll learn (practice, course, mentor, feedback).",
            "Set a weekly routine.",
            "Say how you'll know you improved.",
        ),
    ),
    Template(
        "e-seen",
        "easy",
        "knowledge",
        "Excellent {skill}",
        "Describe an example of excellent {skill} that you've seen or done. What made it excellent?",
        _skills,
        lambda p, s: (EXAMPLE, WHY, uses_job(p, s["skill"]), STEPS),
        (
            "Set up the example in a sentence.",
            "Point to two or three specific things that made it excellent.",
            "Say what you'd copy from it.",
        ),
    ),
    Template(
        "e-tool",
        "easy",
        "knowledge",
        "Working with {tool}",
        "How comfortable are you with {tool}? Describe how you've used it, or how you'd get up to speed.",
        _tools,
        lambda p, s: (
            uses_job(p, s["tool"], label=f"Talks concretely about {s['tool']}"),
            EXAMPLE,
            GROWTH,
            WHY,
        ),
        (
            "Be honest about your level.",
            "Give a concrete example of using it (or something similar).",
            "If you're new to it, give a specific plan to learn it.",
            "Say what it helps you do in the job.",
        ),
    ),
    Template(
        "e-tool-mistake",
        "easy",
        "knowledge",
        "Catching mistakes with {tool}",
        "What's a mistake someone could make with {tool}, and how would you catch it?",
        _tools,
        lambda p, s: (uses_job(p, s["tool"]), STEPS, WHY, FOLLOW_UP),
        (
            "Name a realistic mistake.",
            "Describe the check that catches it.",
            "Explain the impact if it slipped through.",
        ),
    ),
    Template(
        "e-inform",
        "easy",
        "knowledge",
        "Keeping {people} informed",
        "How do you keep {people} informed during a normal day?",
        _people,
        lambda p, s: (communicate(p, s["people"]), STEPS, WHY, EXAMPLE),
        (
            "Say what {people} need to know and when.",
            "Describe how you share it (in person, message, notes).",
            "Give an example of an update you'd give.",
        ),
    ),
    Template(
        "e-needs",
        "easy",
        "knowledge",
        "What {people} need",
        "What do {people} need most from {a_role}?",
        _people,
        lambda p, s: (uses_job(p, s["people"], label=f"Focuses on {s['people']}"), WHY, EXAMPLE, STEPS),
        (
            "Name the two or three things that matter most to {people}.",
            "Explain why each matters.",
            "Say how you deliver each one in practice.",
        ),
    ),
    Template(
        "e-metric",
        "easy",
        "knowledge",
        "What {metric} tells you",
        "What does tracking {metric} tell you about how well {a_role} is doing?",
        _metrics,
        lambda p, s: (
            uses_job(p, s["metric"], label=f"Explains {s['metric']} correctly"),
            WHY,
            MEASURE,
            EXAMPLE,
        ),
        (
            "Say what the number measures.",
            "Explain what good and bad look like.",
            "Name one thing {a_role} does that moves it.",
        ),
    ),
    Template(
        "e-metric-early",
        "easy",
        "knowledge",
        "Spotting slipping {metric}",
        "How would you notice early if {metric} started heading the wrong way?",
        _metrics,
        lambda p, s: (MEASURE, ASSESS, communicate(p), FOLLOW_UP),
        (
            "Describe what you'd watch and how often.",
            "Say what early warning signs look like.",
            "Explain who you'd tell and what you'd do first.",
        ),
    ),
    Template(
        "e-general",
        "easy",
        "general",
        "{_title}",
        "{_prompt}",
        _general(GENERAL_PROMPTS),
        _general_rubric,
        (
            "Keep it to about one or two minutes.",
            "Make it specific to {a_role}.",
            "Back up claims with a short example.",
        ),
    ),
    # ---------------------------------------------------------------- medium (situations and behavior)
    Template(
        "m-walk",
        "medium",
        "situational",
        "Handle it: {situation}",
        "{Situation}. Walk me through what you would do.",
        _situations,
        lambda p, s: (ASSESS, PRIORITIZE, communicate(p), uses_job(p), FOLLOW_UP),
        (
            "Assess: what you'd check first.",
            "Prioritize: what's most urgent or risky.",
            "Act: the specific steps, using the job's tools and skills.",
            "Communicate: who you'd update ({people_list}).",
            "Follow up: what you'd document or change afterwards.",
        ),
    ),
    Template(
        "m-update",
        "medium",
        "situational",
        "Updating {people}: {short}",
        "{Situation}, and you also need to keep {people} informed. How do you handle both?",
        _situation_people(8),
        lambda p, s: (PRIORITIZE, communicate(p, s["people"]), ASSESS, uses_job(p), FOLLOW_UP),
        (
            "Decide what can't wait.",
            "Give {people} a short, honest update and when they'll hear next.",
            "Handle the situation step by step.",
            "Close the loop afterwards.",
        ),
    ),
    Template(
        "m-pressure",
        "medium",
        "behavioral",
        "{skill} under pressure",
        "Tell me about a time you had to use {skill} under pressure.",
        _skills,
        lambda p, s: (*STAR, uses_job(p, s["skill"])),
        (
            "Situation: what made it high-pressure.",
            "Task: what was on you.",
            "Action: what you did, step by step, with {skill}.",
            "Result: the outcome.",
            "Reflection: what you'd keep or change.",
        ),
    ),
    Template(
        "m-mistake",
        "medium",
        "behavioral",
        "A mistake in {skill}",
        "Tell me about a time you made a mistake related to {skill}. What happened, and what did you change?",
        _skills,
        lambda p, s: (STAR[0], ETHICS, STAR[2], STAR[3], STAR[4]),
        (
            "Pick a real but recoverable mistake.",
            "Own it clearly, without blaming others.",
            "Explain how you fixed it.",
            "Say what you changed so it won't happen again.",
        ),
    ),
    Template(
        "m-balance",
        "medium",
        "situational",
        "Balancing {skill} and {skill2}",
        "How would you balance {skill} with {skill2} when you don't have time to do both well?",
        _skill_pairs,
        lambda p, s: (TRADE_OFF, uses_job(p, s["skill"], s["skill2"]), WHY, communicate(p), EXAMPLE),
        (
            "Say what you'd look at to decide.",
            "Explain what you'd do first and what you'd do “good enough”.",
            "Mention who you'd tell about the trade-off.",
            "Give an example.",
        ),
    ),
    Template(
        "m-disagree",
        "medium",
        "behavioral",
        "Disagreeing with {people} on {skill}",
        "Describe how you'd handle a disagreement with {people} about {skill}.",
        _people_skills,
        lambda p, s: (RESPECT, uses_job(p, s["skill"]), TRADE_OFF, communicate(p, s["people"]), FOLLOW_UP),
        (
            "Listen first and restate their view.",
            "Explain your reasoning with facts.",
            "Look for common ground or a test.",
            "Agree on next steps and check back.",
        ),
    ),
    Template(
        "m-improve",
        "medium",
        "situational",
        "Improving {metric}",
        "What steps would you take to improve {metric} over the next three months?",
        _metrics,
        lambda p, s: (ASSESS, MEASURE, STEPS, communicate(p), uses_job(p)),
        (
            "Find out the current number and the main causes.",
            "Pick two or three changes.",
            "Set a target and how you'll track it weekly.",
            "Say who you'd involve.",
        ),
    ),
    Template(
        "m-corners",
        "medium",
        "situational",
        "A coworker cutting corners on {skill}",
        "A coworker keeps cutting corners on {skill}. What do you do?",
        _skills,
        lambda p, s: (RESPECT, ETHICS, communicate(p), uses_job(p, s["skill"]), FOLLOW_UP),
        (
            "Talk to them privately first and listen.",
            "Explain the risk in concrete terms.",
            "Escalate if it continues or is unsafe.",
            "Follow up.",
        ),
    ),
    Template(
        "m-train",
        "medium",
        "leadership",
        "Teaching {skill}",
        "How would you train a new teammate in {skill}?",
        _skills,
        lambda p, s: (
            STEPS,
            uses_job(p, s["skill"]),
            RubricPoint(
                "Checks that they really learned it",
                (
                    r"\bpractice",
                    r"\bshadow",
                    r"\bwatch (them|me)\b",
                    r"\bfeedback",
                    r"\bcheck",
                    r"\bquiz",
                    r"\bask them\b",
                    r"\bhands[- ]on\b",
                    r"\bdemonstrat",
                    r"\bobserv",
                ),
                "Say how you'd check they can do it: let them practice while you watch, then give feedback.",
            ),
            WHY,
        ),
        (
            "Explain the why before the how.",
            "Show, then let them try while you watch.",
            "Give feedback and a checklist.",
            "Check back after a week.",
        ),
    ),
    # ---------------------------------------------------------------- hard (complex judgment and leadership)
    Template(
        "h-both",
        "hard",
        "situational",
        "Two at once: {short} / {short2}",
        "Two things happen at once: {situation}, and {situation2}. What do you do first, and why?",
        _situation_pairs,
        lambda p, s: (PRIORITIZE, TRADE_OFF, communicate(p), uses_job(p), FOLLOW_UP),
        (
            "Say which one you handle first and the reason (safety, impact, time).",
            "Say how you cover the other one (delegate, ask for help, set expectations).",
            "Communicate with {people_list}.",
            "Review afterwards so you're better prepared.",
        ),
    ),
    Template(
        "h-hardest",
        "hard",
        "behavioral",
        "Your hardest {skill} challenge",
        "Tell me about the hardest situation you've faced involving {skill}. What was at stake, and what was the result?",
        _skills,
        lambda p, s: (*STAR, uses_job(p, s["skill"])),
        (
            "Make the stakes clear early.",
            "Show your own decisions, including any you'd change.",
            "Quantify the result.",
            "End with what it taught you.",
        ),
    ),
    Template(
        "h-skip",
        "hard",
        "situational",
        "Pressure to skip steps in {skill}",
        "Your manager asks you to skip part of your usual {skill} process to save time. How do you respond?",
        _skills,
        lambda p, s: (ETHICS, RESPECT, TRADE_OFF, communicate(p), uses_job(p, s["skill"])),
        (
            "Understand why they're asking.",
            "Explain the risk of skipping that step, specifically.",
            "Offer a faster option that keeps the important checks.",
            "Escalate if it's unsafe or against the rules.",
        ),
    ),
    Template(
        "h-90",
        "hard",
        "situational",
        "90 days to improve {metric}",
        "You have 90 days and no extra budget to improve {metric}. Lay out your plan and how you'd measure success.",
        _metrics,
        lambda p, s: (ASSESS, MEASURE, STEPS, TRADE_OFF, communicate(p)),
        (
            "Weeks 1-2: measure the baseline and find the biggest causes.",
            "Weeks 3-8: try two or three low-cost changes.",
            "Weeks 9-12: keep what works and make it routine.",
            "Report progress with numbers.",
        ),
    ),
    Template(
        "h-pushback",
        "hard",
        "situational",
        "Disagreeing with {people}: {short}",
        "{Situation}, and you and {people} disagree on what to do next. How do you move forward?",
        _situation_people(5),
        lambda p, s: (RESPECT, PRIORITIZE, communicate(p, s["people"]), TRADE_OFF, FOLLOW_UP),
        (
            "Deal with anything urgent or unsafe first.",
            "Hear their reasons and share yours with facts.",
            "Agree on a decision or who decides.",
            "Follow up and learn from it.",
        ),
    ),
    Template(
        "h-bad-news",
        "hard",
        "behavioral",
        "Bad news for {people}",
        "Describe a time you had to deliver bad news to {people}. How did you prepare, and how did it land?",
        _people,
        lambda p, s: (
            STAR[0],
            RubricPoint(
                "Prepares and delivers it clearly and kindly",
                (
                    r"\bprepar",
                    r"\bdirect",
                    r"\bhonest",
                    r"\bclear",
                    r"\bcalm",
                    r"\bempath",
                    r"\bin person\b",
                    r"\bexplain",
                    r"\bplan\b",
                    r"\boptions\b",
                ),
                "Say how you prepared (facts, options) and how you said it: clearly, early and with empathy.",
            ),
            STAR[2],
            STAR[3],
            STAR[4],
        ),
        (
            "Context: what the bad news was.",
            "Preparation: facts and options you brought.",
            "Delivery: direct, honest and kind.",
            "Result and what you learned.",
        ),
    ),
    Template(
        "h-lead",
        "hard",
        "leadership",
        "Raising the bar on {skill}",
        "If you were leading a team of people in this job, how would you raise the standard of {skill} across the team?",
        _skills,
        lambda p, s: (ASSESS, STEPS, MEASURE, uses_job(p, s["skill"]), RESPECT),
        (
            "Find out where the team is today.",
            "Set a clear standard and show what good looks like.",
            "Train, coach and give feedback.",
            "Measure progress and recognize improvement.",
        ),
    ),
    Template(
        "h-hidden",
        "hard",
        "situational",
        "An unnoticed error in {skill}",
        "What would you do if you realized, after the fact, that you'd made an error in {skill} that nobody else noticed?",
        _skills,
        lambda p, s: (ETHICS, PRIORITIZE, communicate(p), FOLLOW_UP),
        (
            "Check the impact quickly.",
            "Tell the right person promptly. Don't hide it.",
            "Fix it and limit the damage.",
            "Change your process so it doesn't recur.",
        ),
    ),
    Template(
        "h-rollout",
        "hard",
        "leadership",
        "Leading through a change in {tool}",
        "Your workplace changes how it uses {tool}, and it's slowing everyone down and hurting morale. How do you help?",
        _tools,
        lambda p, s: (RESPECT, ASSESS, STEPS, communicate(p), MEASURE),
        (
            "Listen to what's actually hard.",
            "Find quick wins (training, tips, cheat sheets).",
            "Raise real problems with the people who can fix them.",
            "Track whether things get better.",
        ),
    ),
    Template(
        "h-persuade",
        "hard",
        "behavioral",
        "Changing minds about {skill}",
        "Tell me about a time you changed someone's mind about how to approach {skill}.",
        _skills,
        lambda p, s: (STAR[0], RESPECT, STAR[2], STAR[3], STAR[4]),
        (
            "Set up the disagreement.",
            "Show you understood their view.",
            "Explain the evidence you used.",
            "Share the result and what you learned.",
        ),
    ),
)


# ----------------------------------------------------------------------------------------------
# Generation
# ----------------------------------------------------------------------------------------------

TIPS = {
    "behavioral": (
        "Use the STAR method: Situation, Task, Action, Result.",
        "Say “I”, not just “we”: they're hiring you.",
        "Aim for about 150-300 words (one to two minutes out loud).",
    ),
    "situational": (
        "Think out loud: assess, prioritize, act, communicate, follow up.",
        "Name the real tools and people involved in the job.",
        "It's fine to say what you'd ask before acting.",
    ),
    "knowledge": (
        "Start with a one-sentence answer, then back it up.",
        "Use the job's real terms and tools.",
        "A short example makes it memorable.",
    ),
    "leadership": (
        "Show how you'd bring people with you, not just give orders.",
        "Include how you'd measure progress.",
        "Mention how you'd handle resistance.",
    ),
    "motivation": (
        "Be specific about this job, not jobs in general.",
        "Connect your story to what the role needs.",
        "Keep it positive and under two minutes.",
    ),
}


def _short(clause: str, words: int = 5) -> str:
    """A few words of a situation for list titles: 'a patient's vital signs drop suddenly …'."""
    parts = clause.split()
    return " ".join(parts[:words]) + (" …" if len(parts) > words else "")


def _fill(text: str, p: JobProfile, slots: Slots) -> str:
    values = {
        "role": p.role,
        "a_role": f"{p.article} {p.role}",
        "people_list": " and ".join(p.people[:2]),
        "tool_list": ", ".join(p.tools[:3]),
        **{k: v for k, v in slots.items()},
    }
    if "situation" in slots:
        values["Situation"] = slots["situation"][0].upper() + slots["situation"][1:]
        values["short"] = _short(slots["situation"])
    if "situation2" in slots:
        values["short2"] = _short(slots["situation2"])
    values.setdefault("people", p.people[0])
    # General prompts are themselves templates.
    for key in ("_title", "_prompt"):
        if key in values:
            values[key] = values[key].format(**values)
    return text.format(**values)


def _build(p: JobProfile, t: Template, suffix: str, slots: Slots) -> Question:
    kind = slots.get("_kind", t.kind)
    title = _fill(t.title, p, slots)
    return Question(
        id=f"{t.key}-{suffix}",
        track=p.slug,
        difficulty=t.difficulty,
        kind=kind,
        title=title[0].upper() + title[1:],
        prompt=_fill(t.prompt, p, slots),
        tags=tuple(v for k, v in slots.items() if not k.startswith("_")),
        rubric=t.rubric(p, slots),
        outline=tuple(_fill(line, p, slots) for line in t.outline),
        tips=TIPS[kind],
    )


@lru_cache(maxsize=256)
def generated_questions(track: str) -> tuple[Question, ...]:
    """All generated questions for a career (version 1, retired ones included), easy first.
    Within a level, templates are interleaved so the first few questions shown cover different
    kinds of question."""
    p = CATALOG[track]
    out: list[Question] = []
    for level in LEVELS:
        streams = [
            [(suffix, slots) for suffix, slots in t.slots(p)] for t in TEMPLATES if t.difficulty == level
        ]
        templates = [t for t in TEMPLATES if t.difficulty == level]
        picked: list[Question] = []
        depth = 0
        while len(picked) < PER_LEVEL and any(depth < len(s) for s in streams):
            for t, stream in zip(templates, streams, strict=True):
                if depth < len(stream) and len(picked) < PER_LEVEL:
                    picked.append(_build(p, t, *stream[depth]))
            depth += 1
        out.extend(picked)
    return tuple(out)


CORRECTABLE_FIELDS = ("title", "prompt", "tips", "outline")


def content_key(track: str, question_id: str) -> str:
    return f"{track}/{question_id}"


def _corrected(q: Question, version: int | None = None) -> Question:
    """Apply published corrections up to `version` (default: all of them)."""
    corrections = content_state.current().corrections.get(("question", content_key(q.track, q.id)), [])
    changes: dict = {}
    latest = 1
    for c in corrections:
        if version is not None and c.version > version:
            break
        changes.update(
            {
                k: (tuple(v) if isinstance(v, list) else v)
                for k, v in c.fields.items()
                if k in CORRECTABLE_FIELDS
            }
        )
        latest = c.version
    return replace(q, **changes, version=latest) if corrections and latest > 1 else q


def is_retired(track: str, question_id: str) -> bool:
    return ("question", content_key(track, question_id)) in content_state.current().retired


def questions_for(track: str) -> tuple[Question, ...]:
    """The questions offered for practice: current versions, retired ones left out."""
    return tuple(_corrected(q) for q in generated_questions(track) if not is_retired(track, q.id))


def get_question(track: str, question_id: str, version: int | None = None) -> Question | None:
    """One question, retired or not (history and saved items still need it), at its current
    version or, with `version`, as it was then."""
    if track not in CATALOG:
        return None
    base = next((q for q in generated_questions(track) if q.id == question_id), None)
    return _corrected(base, version) if base else None
