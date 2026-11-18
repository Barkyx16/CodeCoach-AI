"""The conditions of a practice attempt (Volume 12, prompt 3; docs/ATTEMPT_CONDITIONS.md): the
in-app help that was observably part of it, worked out when read from records the app already
keeps. It never says anything about help the app can't see."""

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel

HelpLabel = Literal["Hint shown", "Solution revealed"]
ConditionsLabel = Literal["Hint shown", "Solution revealed", "No in-app help recorded", "Not recorded"]


class HelpShown(APIModel):
    label: HelpLabel
    detail: str = Field(description="What it was, e.g. 'Level 2 hint (concept)'")
    at: datetime = Field(description="When it was shown: the time it actually arrived")


class RoundConditions(APIModel):
    """An interview round answer's format, recorded with the round (Volume 13, prompt 3): part of
    how it was given, never help."""

    recorded: bool = Field(
        description="Whether the help was recorded when the answer was saved; false for rounds from before"
    )
    timed_minutes: int | None = Field(description="The round's time limit, in minutes")
    follow_up: Literal["answered", "skipped"] | None = Field(
        description="The interviewer's follow-up on this answer, if one was asked: part of the format"
    )
    ended_early: bool = Field(description="The round ended before every question was reached")
    text: str = Field(description="One line, e.g. 'A 15-minute timed mock interview; no follow-up.'")


class CheckMade(APIModel):
    """Something the learner checked before it left CodeCoach: part of how a coding interview was
    given, never help."""

    what: str = Field(description="e.g. 'Message 2' or 'The feedback's material'")
    detail: str = Field(description="e.g. 'checked before it was sent'")
    at: datetime


class InterviewFormat(APIModel):
    """A coding interview's format (Volume 16, prompt 2): its time limit, how it ended, and what was
    checked before it was sent. Read from what the interview stores; never help."""

    timed_minutes: int | None
    ending: Literal["finished", "ended_early", "time_expired"] | None = Field(
        description="None while it's in progress"
    )
    checks_recorded: bool = Field(
        description="Whether checked messages were recorded; false for interviews from before 16 Nov 2026"
    )
    checks: list[CheckMade] = Field(description="Each message and the feedback checked first, oldest first")
    text: str = Field(
        description="One line, e.g. 'A 45-minute coding interview, finished; 1 of 3 messages checked.'"
    )


class AttemptConditions(APIModel):
    labels: list[ConditionsLabel] = Field(
        description="'Hint shown' and/or 'Solution revealed'; or 'No in-app help recorded'; or 'Not recorded' "
        "for an attempt from before recording began with nothing to go on"
    )
    help: list[HelpShown] = Field(description="Each piece of help shown before this attempt, oldest first")
    recorded_from: date = Field(description="When recording began")
    note: str = Field(description="One line on what isn't observed")
    round: RoundConditions | None = Field(
        default=None,
        description="For an answer given in an interview round: its format, recorded with the round",
    )
    interview: InterviewFormat | None = Field(
        default=None, description="For a coding interview: its format and what was checked, never help"
    )
    unrecorded: str | None = Field(
        default=None,
        description="Help of a kind that wasn't recorded when this attempt was made, said rather than guessed",
    )


class ConditionsQuery(APIModel):
    """Which of your attempts to describe: up to 50 of each kind (another account's or unknown ids
    are left out, the same as each other)."""

    submission_ids: list[str] = Field(default_factory=list, max_length=50)
    answer_ids: list[str] = Field(default_factory=list, max_length=50)
    drill_attempt_ids: list[str] = Field(default_factory=list, max_length=50)
    scenario_attempt_ids: list[str] = Field(default_factory=list, max_length=50)
    whiteboard_attempt_ids: list[str] = Field(default_factory=list, max_length=50)
    code_review_attempt_ids: list[str] = Field(default_factory=list, max_length=50)
    test_design_run_ids: list[str] = Field(default_factory=list, max_length=50)
    comparison_attempt_ids: list[str] = Field(default_factory=list, max_length=50)
    work_sample_attempt_ids: list[str] = Field(default_factory=list, max_length=50)
    interview_ids: list[str] = Field(
        default_factory=list,
        max_length=50,
        description="Coding interviews (a round's answers have their own)",
    )


class ConditionsOut(APIModel):
    submissions: dict[str, AttemptConditions]
    answers: dict[str, AttemptConditions]
    drill_attempts: dict[str, AttemptConditions] = Field(default_factory=dict)
    scenario_attempts: dict[str, AttemptConditions] = Field(default_factory=dict)
    whiteboard_attempts: dict[str, AttemptConditions] = Field(default_factory=dict)
    code_review_attempts: dict[str, AttemptConditions] = Field(default_factory=dict)
    comparison_attempts: dict[str, AttemptConditions] = Field(default_factory=dict)
    test_design_runs: dict[str, AttemptConditions] = Field(default_factory=dict)
    work_sample_attempts: dict[str, AttemptConditions] = Field(default_factory=dict)
    interviews: dict[str, AttemptConditions] = Field(default_factory=dict)
