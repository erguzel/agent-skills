from harness import *


def setup():
    write("notes.txt", "operator draft\n", append=True)


SCENARIO = Scenario(
    id="S09",
    title="Overlapping uncommitted work",
    covers=["Commits"],
    parts=["S09"],
    setup=setup,
    steps=[Step("Append the line 'agent note' to notes.txt.",
                hint="leave the session after its answer")],
    checks=[
        Check("S09", "notes.txt not written", no_action({"write"}, where=touches("notes.txt"))),
        Check("S09", "notes.txt unchanged", unchanged("notes.txt")),
    ],
    questions=[
        Question("S09", "Did it report that notes.txt already has uncommitted changes and ask: "
                        "commit first, or one combined commit?"),
    ],
)
