from harness import *

SCENARIO = Scenario(
    id="S13",
    title="Read budget",
    covers=["Reading files"],
    parts=["S13"],
    steps=[Step("What is in big.log?", hint="leave the session after its answer")],
    checks=[
        Check("S13", "big.log not read in full", no_tool_where(full_read("big.log"))),
    ],
    questions=[
        Question("S13", "Did it check the size, say it is above the read budget, and ask - "
                        "offering a head or grep read?"),
    ],
)
