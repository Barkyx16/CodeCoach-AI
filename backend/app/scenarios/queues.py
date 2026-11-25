"""Work-queue scenarios (Volume 10, prompt 7): several tasks at once, ordered by the learner.

Two fictional cases, authored and checked in this repository (docs/SCENARIOS.md, "Work queues"):
- an IT support queue where no order is impossible and several strategies are defensible;
- a dispatch queue where a task needs another first and two deadlines can't be missed, with new
  information arriving before work starts, so the second plan is judged on what was known then.

Every dependency and hard deadline is also stated in the task's facts, in plain words: the
learner has everything needed to find a valid order. Times are the case's own estimates.
"""

from app.learn import Reference, Review
from app.scenarios import Dependency, Node, RubricPoint, Scenario, Strategy, Task

_REVIEW = Review(
    status="author_reviewed",
    by="CodeCoach project author",
    on="2026-11-09",
    note="Fictional queue, checked for internal consistency (every order's times and constraints are computed). "
    "Not reviewed by an outside practitioner.",
)

_QUEUE_DOC = Reference(
    title="How work-queue cases are built and checked",
    publisher="CodeCoach repository",
    kind="repository",
    note="docs/SCENARIOS.md, Work queues",
)

_SUPPORT_REASONING = (
    RubricPoint(
        "urgency",
        "Urgency: the fixed times (09:30, 10:00)",
        (
            "09:30",
            "9:30",
            "10:00",
            "10am",
            "deadline",
            "starts at",
            "in time",
            "board meeting",
            "urgent",
            "arrives",
        ),
    ),
    RubricPoint(
        "impact",
        "Impact: who is blocked, and how many",
        (
            "three people",
            "3 people",
            "remote",
            "can't work",
            "cannot work",
            "most people",
            "blocked",
            "shared drive",
        ),
    ),
    RubricPoint(
        "communication",
        "Communication: who you tell what to expect",
        (
            "tell",
            "let them know",
            "let her know",
            "let him know",
            "message",
            "update",
            "workaround",
            "first-floor printer",
            "first floor printer",
            "heads-up",
            "heads up",
        ),
    ),
)

SUPPORT_QUEUE = Scenario(
    id="it-morning-queue",
    track="it-support-specialist",
    version=1,
    changes=("First version.",),
    title="The 08:45 support queue",
    role="IT support specialist (the only one on site until 10:00)",
    objective="Order five requests, say what you'd do first and why, and see which reasonable strategy you followed.",
    minutes=6,
    scope="A fictional office on a Monday morning. Times are the case's estimates, and nothing here is a real "
    "ticket or a real person.",
    start="queue",
    nodes=(
        Node(
            "queue",
            "prioritize",
            "Monday, 08:45: five requests",
            "You're the only IT support person on site until 10:00, and you do one thing at a time. Put the requests "
            "in the order you'd handle them, then say what you'd do first and why.",
            next="done",
            clock="08:45",
            tasks=(
                Task(
                    "vpn",
                    "Remote staff can't connect",
                    (
                        "Since 08:30, three people working from home can't connect to the VPN.",
                        "They can read email on their phones but can't reach the shared drive.",
                        "Renewing the VPN certificate, the likely fix, takes about 20 minutes.",
                    ),
                    minutes=20,
                    consequence="Three people can't do most of their work until it's fixed.",
                ),
                Task(
                    "newhire",
                    "New starter's account",
                    (
                        "Priya starts at 09:30; her manager asked for her account to be ready when she arrives.",
                        "Creating the account and mailbox takes about 15 minutes.",
                    ),
                    minutes=15,
                    due="09:30",
                    consequence="If it isn't ready, Priya waits at reception and her induction starts late.",
                ),
                Task(
                    "board",
                    "Boardroom screen",
                    (
                        "The boardroom screen won't show laptops. The board meets there at 10:00.",
                        "Testing and swapping the cable takes about 15 minutes; a spare is in the IT cupboard.",
                    ),
                    minutes=15,
                    due="10:00",
                    consequence="The board starts without a screen.",
                ),
                Task(
                    "locked",
                    "Locked-out account",
                    (
                        "Tom in sales is locked out after too many password attempts.",
                        "Unlocking him, after checking it's really him, takes about 5 minutes.",
                        "He has a customer call at 11:00.",
                    ),
                    minutes=5,
                ),
                Task(
                    "printer",
                    "Second-floor printer jam",
                    (
                        "The second-floor printer is jammed.",
                        "The first-floor printer works, so people can print there meanwhile.",
                        "Clearing the jam takes about 10 minutes.",
                    ),
                    minutes=10,
                ),
            ),
            strategies=(
                Strategy(
                    "people",
                    "Most people blocked first",
                    (("vpn", "newhire"), ("vpn", "board"), ("vpn", "printer")),
                    "Three people can't work right now, so the VPN restores the most work soonest. It gives up margin "
                    "on the fixed times: if the VPN takes longer than 20 minutes, Priya's account can be late.",
                ),
                Strategy(
                    "fixed",
                    "Fixed times first",
                    (("newhire", "vpn"), ("board", "vpn")),
                    "Priya's 09:30 start and the 10:00 meeting can't move, so doing them first guarantees both. It "
                    "gives up: the three remote staff wait about half an hour longer.",
                ),
                Strategy(
                    "quick",
                    "A five-minute unblock first",
                    (("locked", "vpn"), ("locked", "newhire"), ("locked", "board")),
                    "Tom's unlock frees a person in five minutes and barely delays anything else. It gives up five "
                    "minutes on everything after it, which only matters if something overruns.",
                ),
            ),
            rubric=_SUPPORT_REASONING,
        ),
        Node(
            "done",
            "ending",
            "Queue cleared",
            "At the case's estimates, every order clears the queue by 09:50. What changes is who waits, and for how "
            "long.",
            outcome="Queue cleared by 09:50 (simulated)",
            debrief="There's no single right order here. Most people first, fixed times first and a quick unblock "
            "first are all defensible: what matters is that your reasons match the facts (who's blocked, what has a "
            "fixed time) and that you tell people what to expect, like pointing them to the first-floor printer.",
        ),
    ),
    required_endings=("done",),
    references=(_QUEUE_DOC,),
    review=_REVIEW,
)

_DISPATCH_REASONING = (
    RubricPoint(
        "urgency",
        "Urgency: the times that can't move",
        (
            "10:00",
            "09:00",
            "9:00",
            "09:15",
            "9:15",
            "deadline",
            "slot",
            "in time",
            "urgent",
            "released",
            "sports day",
        ),
    ),
    RubricPoint(
        "impact",
        "Impact: who waits, and what's lost if it slips",
        (
            "pickers",
            "six",
            "idle",
            "waiting",
            "school",
            "40 boxes",
            "10 boxes",
            "only truck",
            "no other truck",
        ),
    ),
    RubricPoint(
        "communication",
        "Communication: who you call or update",
        ("call", "tell", "let the", "confirm with", "update", "phone", "reply", "know when", "email"),
    ),
)

_PICK_FACTS = (
    "Six pickers are waiting; they can't pick anything until they have the pick list.",
    "Making the pick list takes about 15 minutes.",
)
_LABEL_FACTS = (
    "Every box needs a shipping label.",
    "The label system reads the box count from the pick list, so it can't print labels until the pick list exists.",
    "Printing takes about 10 minutes.",
)
_TRUCK_FACTS = (
    "The carrier holds the 11:00 slot only until 09:00. An unconfirmed slot is released, and there's no other truck "
    "today.",
    "Confirming takes about 5 minutes on the phone.",
)
_RETURNS_FACTS = (
    "A pallet of returns blocks dock 2, where the 11:00 truck loads.",
    "Moving it with the forklift driver takes about 25 minutes.",
)
_SUPPLIER_FACTS = (
    "A supplier asks which day this week they can deliver.",
    "A reply any time today is fine. It takes about 10 minutes.",
)
_LABELS_NEED_PICK = Dependency("pick", "labels", "the label system reads the box count from the pick list.")

DISPATCH_QUEUE = Scenario(
    id="logistics-dispatch-queue",
    track="logistics-coordinator",
    version=1,
    changes=("First version.",),
    title="Dispatch before the 11:00 truck",
    role="Logistics coordinator at a warehouse",
    objective="Plan a morning where some tasks need others first and some can't happen late, then re-plan when "
    "new information arrives.",
    minutes=8,
    scope="A fictional warehouse and a fictional school order. Times are the case's estimates; a real dispatch "
    "depends on your site's systems and carriers.",
    start="plan",
    nodes=(
        Node(
            "plan",
            "prioritize",
            "08:00: plan the morning",
            "Hillside Primary School's order of 40 boxes of sports kit goes on the 11:00 truck. You do one task at a "
            "time. Put the tasks in order, then say what you'd do first and why.",
            next="call",
            invalid_next="stalled_plan",
            clock="08:00",
            tasks=(
                Task("pick", "Make the pick list", _PICK_FACTS, minutes=15),
                Task("labels", "Print the shipping labels", _LABEL_FACTS, minutes=10),
                Task(
                    "truck",
                    "Confirm the 11:00 truck",
                    _TRUCK_FACTS,
                    minutes=5,
                    due="09:00",
                    due_is_hard=True,
                    consequence="After 09:00 the slot is gone and nothing ships today.",
                ),
                Task("returns", "Clear the returns pallet from dock 2", _RETURNS_FACTS, minutes=25),
                Task("supplier", "Reply to a supplier", _SUPPLIER_FACTS, minutes=10),
            ),
            dependencies=(_LABELS_NEED_PICK,),
            strategies=(
                Strategy(
                    "pickers",
                    "Get the pickers moving first",
                    (("pick", "truck"), ("pick", "returns"), ("pick", "supplier")),
                    "Six people are waiting on one list; sending it first means nobody stands idle. It gives up some "
                    "margin on the truck, so confirm it soon after.",
                ),
                Strategy(
                    "slot",
                    "Secure the truck first",
                    (("truck", "pick"), ("truck", "labels")),
                    "Five minutes on the phone protects the only truck today; without it nothing else ships. It gives "
                    "up: six pickers wait five minutes longer.",
                ),
            ),
            rubric=_DISPATCH_REASONING,
        ),
        Node(
            "stalled_plan",
            "info",
            "The plan doesn't hold",
            "Your order can't work as it stands: the step above says which constraint it breaks. Before you start, "
            "the phone rings.",
            next="call",
        ),
        Node(
            "call",
            "info",
            "08:10: new information",
            "Before any work has started, the school calls: sports day moved to this morning. They need 10 of the 40 "
            "boxes by 10:00. A courier can take them if it's booked by 09:15, and the courier's booking form asks "
            "for the label numbers. The other 30 boxes can still go on the 11:00 truck.",
            next="replan",
        ),
        Node(
            "replan",
            "prioritize",
            "08:10: re-plan with what you know now",
            "There's one more task. Put all six in order, then say what you'd do first and why.",
            next="shipped",
            invalid_next="stalled",
            clock="08:10",
            tasks=(
                Task(
                    "pick",
                    "Make the pick list (the 10 urgent boxes first)",
                    (*_PICK_FACTS, "You can list the 10 urgent boxes first; it takes the same time."),
                    minutes=15,
                ),
                Task("labels", "Print the shipping labels", _LABEL_FACTS, minutes=10),
                Task(
                    "courier",
                    "Book the courier for the 10 urgent boxes",
                    (
                        "The courier must be booked by 09:15 to deliver by 10:00.",
                        "Its booking form asks for the label numbers, so the labels have to be printed first.",
                        "Booking takes about 5 minutes.",
                    ),
                    minutes=5,
                    due="09:15",
                    due_is_hard=True,
                    consequence="After 09:15 no courier can reach the school by 10:00.",
                ),
                Task(
                    "truck",
                    "Confirm the 11:00 truck",
                    _TRUCK_FACTS,
                    minutes=5,
                    due="09:00",
                    due_is_hard=True,
                    consequence="After 09:00 the slot is gone and the other 30 boxes don't ship today.",
                ),
                Task("returns", "Clear the returns pallet from dock 2", _RETURNS_FACTS, minutes=25),
                Task("supplier", "Reply to a supplier", _SUPPLIER_FACTS, minutes=10),
            ),
            dependencies=(
                _LABELS_NEED_PICK,
                Dependency("labels", "courier", "the courier's booking form asks for the label numbers."),
            ),
            strategies=(
                Strategy(
                    "urgent",
                    "The urgent chain first",
                    (("pick", "truck"), ("labels", "truck"), ("courier", "truck")),
                    "The 10:00 delivery is the new, tightest deadline, and it needs three steps in a row (list, "
                    "labels, courier); doing them first protects it. It gives up: the truck is confirmed later, at "
                    "08:45, still before 09:00.",
                ),
                Strategy(
                    "slot",
                    "Lock in the truck, then the urgent chain",
                    (("truck", "pick"), ("truck", "courier")),
                    "Five minutes secures the only truck for the other 30 boxes, and the courier chain still fits "
                    "before 09:15. It gives up five minutes of margin on the courier.",
                ),
            ),
            rubric=_DISPATCH_REASONING,
        ),
        Node(
            "stalled",
            "ending",
            "The plan stalls",
            "Part of your plan can't happen in the order you chose; the step above says which constraint it breaks "
            "and what that costs in the case.",
            outcome="A hard constraint was broken (simulated)",
            debrief="When a task needs another first, or can't happen after a certain time, those constraints decide "
            "which orders are possible at all: check them before weighing anything else. Among the possible orders "
            "there's more than one reasonable choice; the plans below show two.",
        ),
        Node(
            "shipped",
            "ending",
            "Both deliveries leave",
            "The courier collects the 10 urgent boxes in time for 10:00, and the other 30 load onto the 11:00 truck "
            "from a clear dock.",
            outcome="Everything ships (simulated)",
            debrief="Your second plan met every hard constraint with what you knew at 08:10. Several orders do; the "
            "plans below show which reasonable strategy yours followed and what another would have traded.",
        ),
    ),
    required_endings=("stalled", "shipped"),
    references=(_QUEUE_DOC,),
    review=_REVIEW,
)

QUEUES: tuple[Scenario, ...] = (SUPPORT_QUEUE, DISPATCH_QUEUE)
