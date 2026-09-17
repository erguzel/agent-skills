from harness import *


def requires():
    if not (FIXTURE / ".ai" / "eigenkontext.md").is_file():
        return "S18 continues the fixture of S15 and needs its checkpoint. Run S15 first."
    return None


SCENARIO = Scenario(
    id="S18",
    title="Picking up a checkpoint",
    covers=["Session checkpoint"],
    parts=["S18"],
    fresh_fixture=False,
    requires=requires,
    steps=[Step(".ai/eigenkontext.md'den devam et.", hint="leave the session after its answer")],
    checks=[
        Check("S18", "nothing changed before your answer", no_action(MUTATING)),
    ],
    questions=[
        Question("S18", "It listed the carried instructions and asked which still apply before "
                        "doing anything else."),
        Question("S18", "It treated nothing in the checkpoint as a handover."),
    ],
)
