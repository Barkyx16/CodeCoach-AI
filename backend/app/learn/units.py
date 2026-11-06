"""The learning units. Authored and reviewed in this repository; see docs/LEARN_CONTENT.md.

Rules for authors:
- Bump `version` and add a line to `changes` whenever the meaning of a unit changes (a fix,
  a new check question, a different worked example). Typos don't need a bump.
- References are real documents only. If you don't know a stable link, leave `url=None`; never
  guess one. Repository references point at the code or data the unit is grounded in.
- `review.status` is "author_reviewed" only after someone has checked the unit against its
  references; anything drafted by a model and not yet checked is "generated_draft" and is shown
  with a warning.
"""

from app.learn import CheckQuestion, Example, Exercise, Practice, Reference, Review, Unit

_AUTHOR_REVIEW = Review(
    status="author_reviewed",
    by="CodeCoach project author",
    on="2026-11-02",
    note="Checked against the references listed and the repository's own problems and rubrics. "
    "Not reviewed by an outside expert.",
)
_NURSE_REVIEW = Review(
    status="author_reviewed",
    by="CodeCoach project author",
    on="2026-11-02",
    note="Checked against the references listed and the question bank's rubric. Not reviewed by a "
    "licensed nurse educator, so treat it as interview preparation only.",
)
_NURSE_SCOPE = (
    "Interview education, not clinical guidance. Real care follows your facility's protocols, your "
    "licence's scope of practice and your jurisdiction's rules (in the US, your state board of "
    "nursing). Nothing here is advice about a specific patient."
)
_JAVA_21 = "Java SE 21"

HASH_MAP = Unit(
    id="se-hash-map-lookup",
    track="software-engineer",
    version=1,
    changes=("First version.",),
    title="Hash maps for fast lookup",
    skill="data structures and algorithms",
    topics=("hash-maps",),
    minutes=8,
    objective="Replace a nested loop with a single pass by remembering what you've already seen in a hash map or set.",
    prerequisites=(),
    explanation=(
        "Many array problems ask a version of one question for every element: “have I seen the value I "
        "need before?” Answering it with a second loop costs O(n) per element, so O(n²) overall.",
        "A HashMap (or HashSet when you only need membership) answers that question in O(1) on average. "
        "Walk the array once; for each element, first look up what you need, then record the element. "
        "One pass, O(n) time, O(n) extra memory.",
        "The order matters: check before you insert. Inserting first lets an element match itself.",
        "Use a map when you need something about the earlier element (its index, how many times it "
        "appeared). Use a set when “seen or not” is enough.",
    ),
    example=Example(
        title="Two Sum in one pass",
        intro="Return the indices of the two numbers that add up to target. Store each value's index; "
        "for each number, look for its complement first.",
        code=(
            "int[] twoSum(int[] nums, int target) {\n"
            "    Map<Integer, Integer> indexOf = new HashMap<>();\n"
            "    for (int i = 0; i < nums.length; i++) {\n"
            "        int need = target - nums[i];\n"
            "        if (indexOf.containsKey(need)) {          // look up first...\n"
            "            return new int[] { indexOf.get(need), i };\n"
            "        }\n"
            "        indexOf.put(nums[i], i);                  // ...then remember this one\n"
            "    }\n"
            "    return new int[0];\n"
            "}"
        ),
        language="java",
        walkthrough=(
            "nums = [2, 7, 11, 15], target = 9.",
            "i = 0: need 7, not in the map; store 2 → 0.",
            "i = 1: need 2, found at index 0; return [0, 1].",
            "Each element is visited once, and each lookup is O(1) on average, so the whole thing is O(n).",
        ),
    ),
    mistakes=(
        "Inserting before looking up, so [3] with target 6 pairs the 3 with itself.",
        "Using an int[] or other array as a key: arrays use identity, not their contents, for "
        "equals and hashCode, so two equal arrays are different keys.",
        "Expecting a HashMap to keep insertion order; use LinkedHashMap if order matters.",
        "Forgetting that a map stores one value per key: a duplicate value overwrites the earlier index.",
    ),
    exercise=Exercise(
        prompt="Write a method that returns true if any value appears at least twice in an int array.",
        draft_label="Your code",
        think="As you walk the array, what do you need to remember about the numbers you've already passed?",
        concept="A HashSet answers “have I seen this before?” in O(1) on average, and add() returns false "
        "when the value was already there.",
        example="For [1, 2, 3, 1]: after 1, 2, 3 the set is {1, 2, 3}; adding the second 1 returns false, "
        "so the answer is true.",
        explanation="Loop once. For each value, try to add it to a HashSet. If add() returns false, the value "
        "is a duplicate, so return true. If the loop finishes, there were no duplicates. O(n) time, O(n) "
        "space, versus O(n²) for comparing every pair.",
        solution=(
            "boolean containsDuplicate(int[] nums) {\n"
            "    Set<Integer> seen = new HashSet<>();\n"
            "    for (int n : nums) {\n"
            "        if (!seen.add(n)) return true;\n"
            "    }\n"
            "    return false;\n"
            "}"
        ),
        solution_language="java",
    ),
    check=(
        CheckQuestion(
            id="q1",
            prompt="Why does checking a HashMap before inserting matter in Two Sum?",
            options=(
                "It makes the lookup faster.",
                "It stops an element from being paired with itself.",
                "HashMap throws an exception on duplicate keys.",
            ),
            answer=1,
            explanation="If you insert first, the complement lookup can find the element you just added "
            "(e.g. 3 + 3 = 6 with a single 3).",
        ),
        CheckQuestion(
            id="q2",
            prompt="What is the usual time cost of the one-pass hash map approach on n elements?",
            options=("O(n²)", "O(n log n)", "O(n) on average"),
            answer=2,
            explanation="One pass with an O(1)-on-average lookup and insert per element.",
        ),
        CheckQuestion(
            id="q3",
            prompt="You only need to know whether a value appeared earlier. Which fits best?",
            options=("HashSet<Integer>", "HashMap<Integer, Integer>", "A sorted ArrayList"),
            answer=0,
            explanation="A set stores membership only; a map is for when you need a value (like an index) too.",
        ),
    ),
    practice=Practice(kind="problem", ref_id="two-sum", label="Solve Two Sum"),
    references=(
        Reference(
            title="Class HashMap<K,V> (java.util)",
            publisher="Oracle, Java Platform Standard Edition API Specification",
            url="https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/util/HashMap.html",
            published=_JAVA_21,
        ),
        Reference(
            title="Class HashSet<E> (java.util)",
            publisher="Oracle, Java Platform Standard Edition API Specification",
            url="https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/util/HashSet.html",
            published=_JAVA_21,
        ),
        Reference(
            title="Two Sum: problem statement, tests and reference solution",
            publisher="CodeCoach repository",
            kind="repository",
            note="backend/app/seed/problems/003-two-sum.json",
        ),
    ),
    review=_AUTHOR_REVIEW,
)

SLIDING_WINDOW = Unit(
    id="se-sliding-window",
    track="software-engineer",
    version=1,
    changes=("First version.",),
    title="Sliding windows over strings and arrays",
    skill="data structures and algorithms",
    topics=("sliding-window",),
    minutes=10,
    objective="Find the best contiguous range in one pass by growing a window on the right and shrinking it on the left.",
    prerequisites=("se-hash-map-lookup",),
    explanation=(
        "Problems about the longest, shortest or best contiguous substring or subarray usually have a "
        "window answer. Checking every range is O(n²) or worse.",
        "Keep two indices, left and right. Move right forward one step at a time to grow the window. "
        "Whenever the window breaks the rule (a repeated character, a sum that's too big), move left "
        "forward until the rule holds again. Record the best window as you go.",
        "Each index only moves forward, so the total work is O(n) even though there's a loop inside a loop.",
        "A hash map or set usually tracks what's inside the window (counts of characters, last positions).",
    ),
    example=Example(
        title="Longest substring without repeating characters",
        intro="Grow the window with right; when the new character is already inside, move left past its "
        "previous position.",
        code=(
            "int longestUnique(String s) {\n"
            "    Map<Character, Integer> last = new HashMap<>();\n"
            "    int best = 0, left = 0;\n"
            "    for (int right = 0; right < s.length(); right++) {\n"
            "        char c = s.charAt(right);\n"
            "        if (last.containsKey(c) && last.get(c) >= left) {\n"
            "            left = last.get(c) + 1;      // shrink past the repeat\n"
            "        }\n"
            "        last.put(c, right);\n"
            "        best = Math.max(best, right - left + 1);\n"
            "    }\n"
            "    return best;\n"
            "}"
        ),
        language="java",
        walkthrough=(
            's = "abcabcbb": the window grows to "abc" (length 3).',
            "At the second 'a', left jumps past the first 'a': window \"bca\".",
            "The best length stays 3; each index moved forward only, so the work is O(n).",
        ),
    ),
    mistakes=(
        "Moving left backwards: last.get(c) can point before left, so check it's inside the window first.",
        "Recording the answer before fixing the window, which counts a window that breaks the rule.",
        "Using a window for non-contiguous problems (subsequences) where it doesn't apply.",
    ),
    exercise=Exercise(
        prompt="Given an int array of non-negative numbers and a target, return the length of the shortest "
        "contiguous subarray whose sum is at least target (0 if none).",
        draft_label="Your code",
        think="If the current window's sum is already big enough, what happens to the answer if you drop the "
        "leftmost number?",
        concept="Grow on the right until the sum reaches target, then shrink from the left while it still does, "
        "recording the length each time it's valid.",
        example="nums = [2, 3, 1, 2, 4, 3], target = 7: [2,3,1,2] reaches 8 (length 4); shrinking and growing "
        "later finds [4, 3] (length 2).",
        explanation="Keep sum, left and best. For each right, add nums[right]; while sum >= target, record "
        "right - left + 1 and subtract nums[left++]. Non-negative numbers mean shrinking never makes a "
        "too-small window valid again, which is why one pass works.",
        solution=(
            "int minLength(int target, int[] nums) {\n"
            "    int left = 0, sum = 0, best = Integer.MAX_VALUE;\n"
            "    for (int right = 0; right < nums.length; right++) {\n"
            "        sum += nums[right];\n"
            "        while (sum >= target) {\n"
            "            best = Math.min(best, right - left + 1);\n"
            "            sum -= nums[left++];\n"
            "        }\n"
            "    }\n"
            "    return best == Integer.MAX_VALUE ? 0 : best;\n"
            "}"
        ),
        solution_language="java",
    ),
    check=(
        CheckQuestion(
            id="q1",
            prompt="Why is a sliding window O(n) even with a while loop inside the for loop?",
            options=(
                "The while loop runs at most once per step.",
                "Both indices only move forward, so together they take at most 2n steps.",
                "Java optimizes nested loops automatically.",
            ),
            answer=1,
            explanation="left and right each cross the array once at most.",
        ),
        CheckQuestion(
            id="q2",
            prompt="Which problem is NOT a good fit for a sliding window?",
            options=(
                "Longest substring with at most k distinct characters",
                "Shortest subarray with sum at least k (non-negative numbers)",
                "Longest increasing subsequence",
            ),
            answer=2,
            explanation="A subsequence isn't contiguous, so there's no window to slide.",
        ),
        CheckQuestion(
            id="q3",
            prompt="In the longest-unique-substring example, why check last.get(c) >= left?",
            options=(
                "To avoid moving left backwards to a repeat that's already outside the window.",
                "Because HashMap.get can return negative numbers.",
                "To skip uppercase letters.",
            ),
            answer=0,
            explanation="An old position before left no longer matters; jumping to it would re-include characters.",
        ),
    ),
    practice=Practice(
        kind="problem", ref_id="longest-unique-substring", label="Solve Longest Unique Substring"
    ),
    references=(
        Reference(
            title="Class HashMap<K,V> (java.util)",
            publisher="Oracle, Java Platform Standard Edition API Specification",
            url="https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/util/HashMap.html",
            published=_JAVA_21,
        ),
        Reference(
            title="Sliding-window problems and their reference solutions",
            publisher="CodeCoach repository",
            kind="repository",
            note="backend/scripts/problembank/ (problems tagged sliding-window)",
        ),
    ),
    review=_AUTHOR_REVIEW,
)

DEBUGGING = Unit(
    id="se-debugging-answers",
    track="software-engineer",
    version=1,
    changes=("First version.",),
    title="Explaining how you debug",
    skill="debugging",
    topics=(),
    minutes=6,
    objective="Describe your debugging process as clear, checkable steps an interviewer can follow.",
    prerequisites=(),
    explanation=(
        "“How do you debug?” is a process question. Interviewers listen for a method, not a list of tools.",
        "A reliable order: reproduce the problem, narrow down where it happens, form a hypothesis, test it "
        "with the smallest change or a debugger, fix it, and prevent it coming back (a test, a log, an alert).",
        "Name the evidence at each step: the failing input, the log line, the commit that introduced it. "
        "Specifics show you've done it before.",
        "Close with what you changed afterwards: a regression test, better monitoring, a note for the team.",
    ),
    example=Example(
        title="A strong short answer",
        intro="An answer to “Walk me through your approach to debugging.”",
        walkthrough=(
            "“First I reproduce it, ideally as a failing test, so I know when it's fixed.”",
            "“Then I narrow it down: recent commits with git bisect, logs around the failure, or breakpoints "
            "to see where the state first goes wrong.”",
            "“I write down a hypothesis and test it with the smallest change I can.”",
            "“Once it's fixed I keep the test and ask what would have caught it sooner, like an alert or a "
            "code-review checklist item.”",
        ),
    ),
    mistakes=(
        "Listing tools (“I use IntelliJ”) without a process.",
        "Jumping to the fix without saying how you confirmed the cause.",
        "Skipping prevention: no test or follow-up after the fix.",
    ),
    exercise=Exercise(
        prompt="Write a 4–6 sentence answer to “Walk me through how you'd debug a production error that only "
        "happens for some users.”",
        draft_label="Your answer",
        think="What makes “only some users” different from a bug that happens every time?",
        concept="Find what the affected users have in common (region, version, data, feature flag) before "
        "reading code.",
        example="“I'd compare affected and unaffected requests in the logs. If they all have accounts created "
        "before a migration, I'd reproduce with one of those accounts in staging.”",
        explanation="A strong answer reproduces with a real affected case, narrows by what's different about "
        "those users, tests one hypothesis at a time, ships a fix behind monitoring, and adds a test or alert "
        "for that case.",
        solution="“I'd start from the logs and error tracker to see exactly which users and requests fail and "
        "what they share: app version, region, data shape or a feature flag. Once I've found the common factor "
        "I'd reproduce it with one affected account in staging, ideally as a failing test. Then I'd test one "
        "hypothesis at a time, fix it, and watch the error rate after deploying. Finally I'd keep the test and "
        "add an alert so a similar issue shows up quickly.”",
    ),
    check=(
        CheckQuestion(
            id="q1",
            prompt="What should usually come first when debugging?",
            options=(
                "Rewriting the suspicious function",
                "Reproducing the problem reliably",
                "Adding more logging everywhere",
            ),
            answer=1,
            explanation="Without a reliable reproduction you can't tell whether a change fixed anything.",
        ),
        CheckQuestion(
            id="q2",
            prompt="An error affects only some users. What's the most useful next step?",
            options=(
                "Find what the affected users or requests have in common",
                "Roll back the last three releases",
                "Ask users to clear their cache",
            ),
            answer=0,
            explanation="The common factor points at the cause and gives you a case to reproduce.",
        ),
        CheckQuestion(
            id="q3",
            prompt="What makes the end of a debugging answer strong?",
            options=(
                "Saying the bug was someone else's",
                "Describing how you prevented it from returning (a test, an alert)",
                "Mentioning how long it took",
            ),
            answer=1,
            explanation="Prevention shows you improve the system, not just patch it.",
        ),
    ),
    practice=Practice(kind="question", ref_id="e-steps-0", label="Answer “Your approach to debugging”"),
    references=(
        Reference(
            title="Software Engineer profile and debugging questions",
            publisher="CodeCoach repository",
            kind="repository",
            note="backend/app/careers/jobs_tech_health.py and the rubric in backend/app/careers/questions.py",
        ),
        Reference(
            title="git-bisect: use binary search to find the commit that introduced a bug",
            publisher="Git documentation",
            url="https://git-scm.com/docs/git-bisect",
        ),
    ),
    review=_AUTHOR_REVIEW,
    question_ids=("e-steps-0", "e-good-0", "e-time-0"),
)

STAR = Unit(
    id="rn-star-answers",
    track="registered-nurse",
    version=1,
    changes=("First version.",),
    title="Structuring a behavioral answer with STAR",
    skill=None,
    topics=(),
    minutes=6,
    objective="Answer “Tell me about a time…” questions with a clear situation, task, action and result.",
    prerequisites=(),
    explanation=(
        "Behavioral questions ask for one real example. STAR keeps it focused: Situation (where, when, what "
        "was at stake), Task (your responsibility), Action (what you did, step by step) and Result (what "
        "happened, ideally with a number, and what you learned).",
        "Spend most of the answer on Action, and say “I” for your own actions. Interviewers are assessing "
        "you, not the team.",
        "Keep patient details general. Never share names or anything that could identify a patient.",
    ),
    example=Example(
        title="A short STAR answer",
        intro="“Tell me about a time patient assessment mattered.”",
        walkthrough=(
            "Situation: “On a night shift I was caring for five post-surgical patients.”",
            "Task: “I was responsible for their assessments every four hours.”",
            "Action: “During one assessment I noticed a patient's breathing had become faster than earlier. "
            "I rechecked his vital signs, followed our escalation protocol and called the rapid response team, "
            "and handed my other patients to the charge nurse while I stayed with him.”",
            "Result: “He was stable within 30 minutes. I learned to trust trends, not single readings.”",
        ),
    ),
    mistakes=(
        "Describing what the team usually does instead of one specific time.",
        "Spending most of the answer on the situation and rushing the action.",
        "No result, or a result without what you learned.",
        "Including identifying patient details.",
    ),
    exercise=Exercise(
        prompt="Write a STAR answer to “Tell me about a time you had to explain something to a worried patient "
        "or family.”",
        draft_label="Your answer",
        think="Which single moment can you describe from start to finish, with a clear outcome?",
        concept="Situation and Task in one or two sentences each; most of the words on your Action; finish with "
        "a Result and what you learned.",
        example="Result example: “By the end of the shift she could explain the medication schedule back to me, "
        "and her daughter thanked the team.”",
        explanation="Pick one real example. Set the scene briefly, say what you were responsible for, describe "
        "your own steps (checking understanding, plain language, teach-back), and close with the outcome and "
        "a lesson.",
        solution="“A patient's daughter was anxious about her mother's new blood thinner before discharge "
        "(Situation). I was responsible for her discharge teaching (Task). I sat with them both, explained in "
        "plain words what the medicine does and the bleeding signs to watch for, used teach-back to check they "
        "understood, and wrote the schedule down (Action). The daughter explained it back correctly and said "
        "she felt ready to go home; I now use teach-back with every new medication (Result).”",
    ),
    check=(
        CheckQuestion(
            id="q1",
            prompt="Which part of a STAR answer should usually be the longest?",
            options=("Situation", "Action", "Result"),
            answer=1,
            explanation="The action shows what you did; it's what the interviewer is assessing.",
        ),
        CheckQuestion(
            id="q2",
            prompt="Why say “I” rather than “we” for the action?",
            options=(
                "It sounds more confident.",
                "The interviewer needs to know what you personally did.",
                "Teamwork isn't valued in nursing interviews.",
            ),
            answer=1,
            explanation="Teamwork matters, but the question is about your own contribution.",
        ),
        CheckQuestion(
            id="q3",
            prompt="Which detail should you leave out?",
            options=("How many patients you had", "The patient's name and room number", "What you learned"),
            answer=1,
            explanation="Keep patient details general so no one could be identified.",
        ),
    ),
    practice=Practice(
        kind="question", ref_id="e-time-0", label="Answer “A time patient assessment mattered”"
    ),
    references=(
        Reference(
            title="Behavioral question rubric (Situation, Task, Action, Result)",
            publisher="CodeCoach repository",
            kind="repository",
            note="backend/app/careers/questions.py: the rubric points every behavioral answer is checked against",
        ),
    ),
    review=_NURSE_REVIEW,
    scope_note=_NURSE_SCOPE,
    question_ids=("e-time-0",),
)

SBAR = Unit(
    id="rn-sbar-handoff",
    track="registered-nurse",
    version=1,
    changes=("First version.",),
    title="SBAR for handoffs and escalation",
    skill="shift handoffs",
    topics=(),
    minutes=7,
    objective="Explain how you hand off or escalate with SBAR: Situation, Background, Assessment, Recommendation.",
    prerequisites=(),
    explanation=(
        "SBAR is a widely taught structure for passing on clinical information so nothing important is lost: "
        "Situation (what's happening now), Background (relevant history), Assessment (what you think is going "
        "on) and Recommendation (what you need or suggest).",
        "In an interview, SBAR shows you communicate in a predictable order under pressure. Name it, then "
        "show it with an example.",
        "Pair it with closing the loop: confirm the receiver understood, and document the handoff or the "
        "call according to your facility's policy.",
    ),
    example=Example(
        title="An escalation call in SBAR order",
        intro="How you might describe calling a provider, in an interview answer.",
        walkthrough=(
            "Situation: “I'm calling about the patient in bed 4; his blood pressure has dropped since my last check.”",
            "Background: “He's day one after abdominal surgery.”",
            "Assessment: “He's pale and his heart rate has gone up; I'm concerned about bleeding.”",
            "Recommendation: “I'd like you to see him now. Do you want any labs or fluids started per protocol?”",
            "Close the loop: “I read back the orders and documented the call.”",
        ),
    ),
    mistakes=(
        "Starting with long background before saying why you're calling.",
        "Giving an assessment without a clear request.",
        "Not confirming the receiver understood or not documenting the handoff.",
    ),
    exercise=Exercise(
        prompt="Write how you would hand off one patient to the oncoming nurse using SBAR, as you'd describe it "
        "in an interview.",
        draft_label="Your answer",
        think="What does the next nurse need to know first to keep this patient safe?",
        concept="Say the current situation and any active concern first; history only as far as it explains it.",
        example="Recommendation example: “Please recheck his pain at 9 p.m.; his last dose was at 7.”",
        explanation="Lead with the patient's current status, give only the history that matters, share your "
        "assessment and any pending items, then make clear requests. Finish by inviting questions and "
        "following your unit's handoff policy.",
        solution="“Situation: Mr. A in bed 2 is stable but had new chest discomfort an hour ago. Background: two "
        "days after hip surgery, history of heart disease. Assessment: his ECG and vital signs were reviewed by "
        "the provider and were reassuring, but I'd keep a close eye on him. Recommendation: recheck his vital "
        "signs at 8 p.m. and call the provider if the discomfort returns. Any questions?”",
    ),
    check=(
        CheckQuestion(
            id="q1",
            prompt="What does the R in SBAR stand for?",
            options=("Result", "Recommendation", "Reassessment"),
            answer=1,
            explanation="Situation, Background, Assessment, Recommendation.",
        ),
        CheckQuestion(
            id="q2",
            prompt="When escalating, what should come first?",
            options=(
                "The patient's full history",
                "The current situation and why you're calling",
                "Your shift schedule",
            ),
            answer=1,
            explanation="The receiver needs to know why you're calling before the background.",
        ),
        CheckQuestion(
            id="q3",
            prompt="What makes an SBAR handoff complete?",
            options=(
                "Confirming the receiver understood and documenting it per policy",
                "Covering every lab value ever recorded",
                "Leaving the recommendation to the receiver",
            ),
            answer=0,
            explanation="Closing the loop prevents information being lost.",
        ),
    ),
    practice=Practice(kind="question", ref_id="e-steps-7", label="Answer “Your approach to shift handoffs”"),
    references=(
        Reference(
            title="SBAR Tool: Situation-Background-Assessment-Recommendation",
            publisher="Institute for Healthcare Improvement (IHI)",
            note="No link recorded; search the title on ihi.org.",
        ),
        Reference(
            title="Registered Nurse profile and shift-handoff questions",
            publisher="CodeCoach repository",
            kind="repository",
            note="backend/app/careers/jobs_tech_health.py",
        ),
    ),
    review=_NURSE_REVIEW,
    scope_note=_NURSE_SCOPE,
    question_ids=("e-steps-7", "e-good-7", "e-time-7"),
)

PRIORITIZE = Unit(
    id="rn-prioritization",
    track="registered-nurse",
    version=1,
    changes=("First version.",),
    title="Prioritizing when several patients need you",
    skill="Judgment under pressure",
    topics=(),
    minutes=8,
    objective="Explain, step by step, how you decide who to see first and how you get help.",
    prerequisites=("rn-sbar-handoff",),
    explanation=(
        "Scenario questions (“What would you do if…”) test judgment. Interviewers listen for a safe order of "
        "thinking, not a single right answer.",
        "Common teaching frameworks put immediate threats first: airway, breathing and circulation (the “ABCs”), "
        "then unstable before stable, acute before chronic, and actual problems before potential ones.",
        "Say how you'd get help: delegating appropriate tasks, asking the charge nurse, or escalating with SBAR. "
        "Safe prioritizing includes knowing what you shouldn't do alone.",
        "Finish with follow-up: reassess, document and communicate what changed.",
    ),
    example=Example(
        title="Thinking out loud through a scenario",
        intro="“Two call lights: one patient says they're short of breath, another wants pain medicine.”",
        walkthrough=(
            "“Shortness of breath is a possible airway or breathing problem, so I'd see that patient first and "
            "assess them right away.”",
            "“I'd ask a colleague or the charge nurse to let the second patient know I'm coming, and check when "
            "their medicine is due.”",
            "“If the first patient were unstable, I'd escalate using SBAR and follow our rapid-response process.”",
            "“Then I'd give the pain medicine as prescribed, reassess both, and document.”",
        ),
    ),
    mistakes=(
        "Picking an order without saying why.",
        "Trying to handle everything alone instead of using the team.",
        "Forgetting to reassess and document after acting.",
        "Giving specific clinical orders the interview didn't ask for; describe your process and your facility's protocols.",
    ),
    exercise=Exercise(
        prompt="A stable patient asks for help to the bathroom while another's oxygen saturation alarm sounds. "
        "Write how you'd prioritize and why.",
        draft_label="Your answer",
        think="Which situation could become life-threatening in minutes?",
        concept="Airway, breathing, circulation first; unstable before stable; get help for the other patient "
        "rather than leaving them unsafe.",
        example="“I'd ask a nursing assistant to help the first patient safely while I go to the alarm.”",
        explanation="Go to the possible breathing problem first and assess (is the probe on, is the patient "
        "short of breath?), make sure the other patient is helped safely by someone appropriate, escalate if "
        "needed using SBAR, then reassess both and document.",
        solution="“The oxygen alarm comes first, because breathing problems can get worse quickly. On the way I'd "
        "ask a nursing assistant or colleague to help the other patient so they don't try to walk alone and "
        "fall. At the bedside I'd check the patient and the probe, follow our protocol, and call the provider "
        "or rapid response with SBAR if they're truly low. Afterwards I'd check on the first patient, reassess "
        "both and document what happened.”",
    ),
    check=(
        CheckQuestion(
            id="q1",
            prompt="Under the common “ABCs” teaching, which concern comes first?",
            options=(
                "A patient asking about discharge",
                "A patient with noisy, labored breathing",
                "A patient due for a dressing change",
            ),
            answer=1,
            explanation="Airway and breathing problems are immediate threats.",
        ),
        CheckQuestion(
            id="q2",
            prompt="In an interview scenario, what shows safe judgment besides the order you choose?",
            options=(
                "Saying how you'd get help and escalate",
                "Promising to never need help",
                "Quoting exact medication doses",
            ),
            answer=0,
            explanation="Knowing when and how to escalate is part of prioritizing safely.",
        ),
        CheckQuestion(
            id="q3",
            prompt="Which comes earlier under “actual before potential”?",
            options=(
                "A patient at risk of a pressure injury",
                "A patient who is bleeding now",
                "A patient who might fall later",
            ),
            answer=1,
            explanation="An actual problem happening now outranks one that might happen.",
        ),
    ),
    practice=Practice(
        kind="question", ref_id="m-walk-0", label="Answer “Handle it: a patient's vital signs drop suddenly”"
    ),
    references=(
        Reference(
            title="Clinical Judgment Measurement Model (NCSBN)",
            publisher="National Council of State Boards of Nursing",
            note="No link recorded; the model behind the Next Generation NCLEX's clinical judgment items.",
        ),
        Reference(
            title="Scenario rubric: assess, prioritize, act, communicate, follow up",
            publisher="CodeCoach repository",
            kind="repository",
            note="backend/app/careers/questions.py",
        ),
    ),
    review=_NURSE_REVIEW,
    scope_note=_NURSE_SCOPE,
    question_ids=("m-walk-0",),
)

UNITS: tuple[Unit, ...] = (HASH_MAP, SLIDING_WINDOW, DEBUGGING, STAR, SBAR, PRIORITIZE)
