# Roadmap

What is being worked on, what waits on it, and what is wanted but not yet
shaped. The list is ordered, not dated: nothing here is a schedule or a
promise, and an item moves when what was learned from the one before it says
so. A decision taken along the way is recorded under `adr/`, not here.

The repository stays private until the whole Core set of behaviour scenarios
has been run in a live agent and reported.

## Now

- **A neutral command classifier.** The harness borrows its classifier from
  the Claude Code adapter's guard (the exception ADR 0003 records). It moves
  into a module inside the skill that names no agent; the guard becomes a thin
  wrapper over it, and a guard that cannot find the module asks for every
  command rather than letting them through. The fixture walk's knowledge of
  where one agent keeps its skills moves into that agent's profile at the
  same time.
- **The Core baseline.** Every Core scenario, run in a live agent as one set,
  for the first time. Each defect this finds in the runner becomes a test
  case. Until it is done, no change to a rule in `SKILL.md` has a baseline to
  be compared against.

## Next

- **A judge for `expected` and `fail_if`.** A run settles its `checks` on its
  own, and a `says` check can match a pattern in what the agent said; the
  prose of `expected` and `fail_if` is still read by a person. The judge adds
  the missing step - a model reading the transcript against that prose - and
  a person is asked only for what comes back undetermined. Its design waits
  on the baseline, which is the first body of transcripts to design against;
  it gets a short specification before code.
- **A second agent.** A profile beside the Claude Code one, as a package with
  its own tests, and an adapter under the skill. It waits on the classifier
  above, so that the second adapter shares the classifier instead of copying
  it.
- **Real use, outside this repository.** The skill has so far governed work on
  itself. Using it on a project that is not its own is what measures its
  friction, and what says whether the read budget, the approval steps and the
  handover of commands are set right.
- **The mechanical layer on Windows and macOS.** `run.py verify` runs in CI on
  Linux only. The hooks are POSIX shell and the guard is Python; neither has
  been tried on Windows.

## Later

- **Attribution patterns for more agents.** Gemini CLI, Windsurf, Cline, Kiro
  and Factory Droid are not covered yet; each needs the form its attribution
  takes, taken from real commits, not guessed.
- **A second skill.** A working agreement for the craft of the code itself,
  separate from vier-augen, which governs the process. It is also what forces
  the choice the architecture leaves open: whether the harness serves many
  skills or each skill brings its own test tree.

## Not planned

- **A ranking of agents.** The scenarios say whether the skill's text holds
  under an agent. Running them across agents to say which agent is better is
  not a goal, and the harness is not built to make that comparison fair.
