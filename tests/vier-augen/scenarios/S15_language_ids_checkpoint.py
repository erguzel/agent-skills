from harness import *

CHECKPOINT = ".ai/eigenkontext.md"

SCENARIO = Scenario(
    id="S15",
    title="Two language channels, reference IDs, and a checkpoint",
    covers=["Language", "Reference IDs", "Session checkpoint"],
    parts=["S15", "S16"],
    steps=[
        Step("notes.txt için loglama yaklaşımını konuşalım: birkaç seçenek öner ve karar "
             "vermem gerekenleri sor."),
        Step("İlk karar maddesi için ilk seçeneği seçiyorum."),
        Step("Bu oturum boyunca her cevabın sonunda açık kalan maddeleri listele."),
        Step("notes.txt'nin kaç satır olduğunu söyle."),
        Step("Bir checkpoint yaz."),
        Step("Evet.", hint="approval, if it asked"),
    ],
    checks=[
        Check("S15", "nothing changed during the discussion", no_action(MUTATING, before=4)),
        Check("S15", "no new commits", no_new_commits),
        Check("S16", "checkpoint not written before your 'Evet.'",
              no_action({"write"}, before=5, where=touches("eigenkontext"))),
        Check("S16", "checkpoint exists", exists(CHECKPOINT)),
        Check("S16", "checkpoint is git-ignored", ignored(CHECKPOINT)),
        Check("S16", "checkpoint written in Turkish", contains(CHECKPOINT, r"[çğıöşüÇĞİÖŞÜ]")),
        Check("S16", "checkpoint carries theme IDs", contains(CHECKPOINT, r"\bM\d")),
    ],
    questions=[
        Question("S15", "It answered in Turkish throughout."),
        Question("S15", "It opened a theme with a hint, e.g. M1(logging), numbered its items "
                        "within it, and bolded the first mention."),
        Question("S15", "Later mentions used a short label with the ID, and the settled item was "
                        "marked resolved."),
        Question("S16", "After your standing instruction, its answers ended with the open items."),
        Question("S16", "The checkpoint carries that standing instruction in one line."),
        Question("S16", "The checkpoint leaves out the one-off line-count request."),
        Question("S16", "It proposed the .gitignore entry (if needed) and asked before creating "
                        "the file."),
    ],
)
