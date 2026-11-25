"""The scenarios. Authored and reviewed in this repository; see docs/SCENARIOS.md for the format.

Each scenario is fictional training material. Outcomes are simulated consequences of the
authored graph, not predictions of what would happen at work.
"""

from app.learn import Reference, Review
from app.scenarios import Node, Option, RubricPoint, Scenario
from app.scenarios.queues import QUEUES

_REVIEW = Review(
    status="author_reviewed",
    by="CodeCoach project author",
    on="2026-11-03",
    note="Checked for internal consistency and against the references listed. Not reviewed by an outside expert.",
)
_NURSE_REVIEW = Review(
    status="author_reviewed",
    by="CodeCoach project author",
    on="2026-11-03",
    note="Checked against the references listed. Not reviewed by a licensed nurse educator and not clinically "
    "validated: it's interview practice, not guidance for real patients.",
)

_STATUS_UPDATE = (
    RubricPoint(
        "impact",
        "What customers saw",
        ("customer", "customers", "checkout", "error", "errors", "fail", "failed", "payments"),
    ),
    RubricPoint(
        "state",
        "Where things stand now",
        ("fixed", "resolved", "rolled back", "rollback", "stable", "recovered", "back to normal", "working"),
    ),
    RubricPoint(
        "time",
        "When it happened or how long",
        ("minutes", "minute", "since", "between", "from", "at ", "for about"),
    ),
    RubricPoint(
        "next",
        "What happens next",
        ("follow up", "follow-up", "postmortem", "post-mortem", "review", "investigat", "update", "monitor"),
    ),
)


def _comms(node_id: str, ending: str) -> Node:
    return Node(
        id=node_id,
        kind="written",
        title="Tell the support team",
        text="Support asks what to tell customers. Write the short update you'd post in their channel (2–4 sentences).",
        next=ending,
        rubric=_STATUS_UPDATE,
    )


INCIDENT = Scenario(
    id="se-incident-checkout",
    track="software-engineer",
    version=1,
    changes=("First version.",),
    title="Checkout errors after a deploy",
    role="On-call software engineer",
    objective="Limit customer impact, restore service and keep people informed.",
    minutes=8,
    scope="A fictional incident at a fictional online shop. Times and outcomes are simulated; real incidents depend on "
    "your team's runbooks and tools.",
    start="start",
    nodes=(
        Node(
            "start",
            "info",
            "The alert",
            "It's 14:05. Five minutes after a deploy, alerts fire: the checkout error rate is 18% (normally under 1%). "
            "The deploy updated the payment client library.",
            next="first",
        ),
        Node(
            "first",
            "choice",
            "Your first move",
            "What do you do first?",
            options=(
                Option(
                    "rollback",
                    "Roll back the deploy, then investigate",
                    "rolled_back",
                    "strong",
                    "When a fresh deploy lines up with the errors, reverting it is the fastest way to stop customer "
                    "impact; you can investigate safely afterwards.",
                ),
                Option(
                    "investigate",
                    "Read the logs to find the root cause before changing anything",
                    "investigating",
                    "risky",
                    "Understanding matters, but every minute spent investigating is another minute of failed "
                    "checkouts when a likely cause can simply be reverted.",
                ),
                Option(
                    "restart",
                    "Restart the checkout servers",
                    "restarted",
                    "risky",
                    "A restart rarely fixes a bad deploy and can wipe useful evidence; it doesn't address the likely cause.",
                ),
            ),
        ),
        Node(
            "rolled_back",
            "info",
            "After the rollback",
            "The rollback finishes at 14:09. The error rate falls to 0.5% within two minutes.",
            next="comms_fast",
        ),
        Node(
            "investigating",
            "info",
            "Twenty minutes in",
            "At 14:25 you find it: the new library times out payment calls after 1 second instead of 10. Errors are "
            "still at 18%.",
            next="second",
        ),
        Node(
            "restarted",
            "info",
            "After the restart",
            "The servers come back at 14:12. The error rate is still 18%.",
            next="investigating",
        ),
        Node(
            "second",
            "choice",
            "Now what?",
            "You know the cause. What do you do?",
            options=(
                Option(
                    "rollback_late",
                    "Roll back the deploy now, then fix the timeout calmly",
                    "rolled_back_late",
                    "acceptable",
                    "Reverting stops the impact; doing it before the investigation would have saved about 20 minutes.",
                ),
                Option(
                    "hotfix",
                    "Write a hotfix that sets the timeout back to 10 seconds and deploy it",
                    "hotfixed",
                    "risky",
                    "A rushed change under pressure adds risk and takes longer than a revert; revert first, then fix "
                    "with a normal review.",
                ),
            ),
        ),
        Node(
            "rolled_back_late",
            "info",
            "Recovered",
            "The rollback finishes at 14:30 and errors return to normal.",
            next="comms_late",
        ),
        Node(
            "hotfixed",
            "info",
            "The hotfix ships",
            "The hotfix needs a review and a full pipeline run. It's live at 14:52 and errors stop.",
            next="comms_hotfix",
        ),
        _comms("comms_fast", "contained"),
        _comms("comms_late", "recovered_late"),
        _comms("comms_hotfix", "recovered_hotfix"),
        Node(
            "contained",
            "ending",
            "Contained quickly",
            "Checkout recovered about 4 minutes after you acted.",
            outcome="Contained in about 6 minutes (simulated)",
            debrief="Reverting the suspect change first kept the impact short. A follow-up review can now find why "
            "the timeout changed and how to catch it before release.",
        ),
        Node(
            "recovered_late",
            "ending",
            "Recovered after a delay",
            "Checkout recovered about 25 minutes after the alert.",
            outcome="Recovered after about 25 minutes (simulated)",
            debrief="The cause was found, but customers kept failing to check out while you investigated. When a "
            "recent deploy is the likely cause, revert first.",
        ),
        Node(
            "recovered_hotfix",
            "ending",
            "Recovered with a rushed fix",
            "Checkout recovered about 47 minutes after the alert.",
            outcome="Recovered after about 47 minutes with an emergency change (simulated)",
            debrief="The hotfix worked, but it took longer than a revert and shipped a change under pressure. Revert, "
            "then fix with a normal review.",
        ),
    ),
    required_endings=("contained", "recovered_late", "recovered_hotfix"),
    references=(
        Reference(
            title="Site Reliability Engineering, chapter 14: Managing Incidents",
            publisher="Google / O'Reilly (2016)",
            url="https://sre.google/sre-book/managing-incidents/",
        ),
        Reference(
            title="Learn unit: Explaining how you debug",
            publisher="CodeCoach repository",
            kind="repository",
            note="/learn/se-debugging-answers",
        ),
    ),
    review=_REVIEW,
)

_SBAR = (
    RubricPoint(
        "situation",
        "Situation: who and what's happening now",
        ("bed 3", "short of breath", "breathing", "breathless", "saturation", "oxygen"),
    ),
    RubricPoint(
        "background",
        "Background: relevant history",
        ("hip", "surgery", "post-op", "postoperative", "day 1", "day one"),
    ),
    RubricPoint(
        "assessment",
        "Assessment: what you think is going on",
        ("concerned", "worried", "think", "deteriorat", "low", "dropping", "fast"),
    ),
    RubricPoint(
        "recommendation",
        "Recommendation: what you need",
        ("come", "see him", "assess", "review", "orders", "rapid response", "now", "please"),
    ),
)

TWO_PATIENTS = Scenario(
    id="rn-two-patients",
    track="registered-nurse",
    version=1,
    changes=("First version.",),
    title="Two call lights at once",
    role="Medical-surgical nurse at the start of a day shift",
    objective="Decide who to see first, escalate appropriately and communicate clearly.",
    minutes=7,
    scope="Fictional interview-practice case, not clinically validated and not instructions for a real patient or "
    "emergency. Real care follows your facility's protocols, your licence's scope of practice and your jurisdiction's rules.",
    start="start",
    nodes=(
        Node(
            "start",
            "info",
            "Start of shift",
            "You're caring for four patients. At 07:15 two call lights come on at the same time.",
            next="report",
        ),
        Node(
            "report",
            "info",
            "What you know",
            "Bed 3: 68 years old, day 1 after hip surgery, says he “can't catch his breath”. Bed 7: 45 years old, "
            "asking for pain medicine; pain 6/10, last dose 4 hours ago and it's due now.",
            next="who",
        ),
        Node(
            "who",
            "choice",
            "Who first?",
            "Which patient do you go to first?",
            options=(
                Option(
                    "bed3",
                    "Bed 3, and ask a colleague to let bed 7 know I'm coming",
                    "assess3",
                    "strong",
                    "A possible breathing problem can worsen within minutes, so it's assessed first; asking a colleague "
                    "to update bed 7 keeps them informed.",
                ),
                Option(
                    "bed7",
                    "Bed 7, because their medicine is due and it'll be quick",
                    "bed7_first",
                    "risky",
                    "Pain matters and should be treated soon, but a possible breathing problem is a potential threat "
                    "to airway and breathing and comes first.",
                ),
            ),
        ),
        Node(
            "bed7_first",
            "info",
            "Meanwhile",
            "While you're with bed 7, a nursing assistant tells you bed 3 looks pale and is breathing fast.",
            next="assess3",
        ),
        Node(
            "assess3",
            "info",
            "At bed 3",
            "He's breathing fast and anxious, and his oxygen saturation is lower than the reading on his chart from the night.",
            next="escalate",
        ),
        Node(
            "escalate",
            "choice",
            "Your next step",
            "What do you do now?",
            options=(
                Option(
                    "call",
                    "Follow the unit protocol, call the provider or rapid response team using SBAR, and stay with him",
                    "sbar",
                    "strong",
                    "Worsening breathing and saturation call for escalation now; SBAR gets the essentials across "
                    "quickly, and staying with him lets you watch for changes.",
                ),
                Option(
                    "wait",
                    "Recheck him in 30 minutes to see whether it settles",
                    "waited",
                    "risky",
                    "Waiting on signs that are getting worse delays help; escalation is expected when vital signs "
                    "deteriorate.",
                ),
            ),
        ),
        Node(
            "sbar",
            "written",
            "Make the call",
            "Write the SBAR call you'd make, as you'd describe it in an interview (3–5 sentences).",
            next="escalated",
            rubric=_SBAR,
        ),
        Node(
            "waited",
            "info",
            "Thirty minutes later",
            "He's more breathless. The charge nurse sees him and calls the rapid response team.",
            next="reflect",
        ),
        Node(
            "reflect",
            "written",
            "Looking back",
            "In 2–4 sentences: what would you do differently, and why?",
            next="delayed",
            rubric=(
                RubricPoint(
                    "earlier",
                    "Escalate sooner",
                    ("earlier", "sooner", "straight away", "immediately", "right away", "not wait"),
                ),
                RubricPoint(
                    "sbar",
                    "Use a structured call (SBAR)",
                    ("sbar", "situation", "background", "recommendation"),
                ),
                RubricPoint(
                    "why",
                    "Say why (worsening signs)",
                    ("worse", "worsening", "deteriorat", "saturation", "breathing"),
                ),
            ),
        ),
        Node(
            "escalated",
            "ending",
            "Help is on the way",
            "The team arrives within minutes and takes over with you.",
            outcome="Escalated promptly (simulated)",
            debrief="You saw a possible breathing problem as the priority, escalated when signs worsened and "
            "communicated in a structured way.",
        ),
        Node(
            "delayed",
            "ending",
            "Help arrived late",
            "The rapid response team arrives 30 minutes later than it could have.",
            outcome="Escalation delayed (simulated)",
            debrief="Waiting to see whether worsening breathing settled delayed help. Interviewers listen for "
            "escalating as soon as signs worsen.",
        ),
    ),
    required_endings=("escalated", "delayed"),
    references=(
        Reference(
            title="SBAR Tool: Situation-Background-Assessment-Recommendation",
            publisher="Institute for Healthcare Improvement (IHI)",
            note="No link recorded; search the title on ihi.org.",
        ),
        Reference(
            title="Learn units: SBAR for handoffs; Prioritizing when several patients need you",
            publisher="CodeCoach repository",
            kind="repository",
            note="/learn/rn-sbar-handoff and /learn/rn-prioritization",
        ),
    ),
    review=_NURSE_REVIEW,
    regulated=True,
)

SCENARIOS: tuple[Scenario, ...] = (INCIDENT, TWO_PATIENTS, *QUEUES)
