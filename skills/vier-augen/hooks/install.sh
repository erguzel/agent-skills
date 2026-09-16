#!/bin/sh
# vier-augen: install this skill's git hooks into the current repository.
# Never overwrites a hook and never edits a hook manager's files: where it
# cannot install, it prints the line to add yourself.
# Usage: run from inside the repository:  sh <this-skill>/hooks/install.sh
set -eu

hooks_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P)
hooks="commit-msg pre-commit pre-push"
top=$(git rev-parse --show-toplevel 2>/dev/null) || {
	echo "install.sh: not inside a git repository." >&2
	exit 1
}

line() { printf '  %-11s sh "%s/%s" "$@" || exit 1\n' "$1:" "$hooks_dir" "$1"; }

configured=$(git config --get core.hooksPath || true)
if [ -n "$configured" ]; then
	resolved=$(cd "$top" && cd "$configured" 2>/dev/null && pwd -P || true)
	if [ "$resolved" = "$hooks_dir" ]; then
		echo "core.hooksPath already points at the vier-augen hooks. Nothing to do."
		exit 0
	fi
	echo "core.hooksPath is set to '$configured' (a hook manager such as husky or"
	echo "lefthook, or a custom directory). Git ignores .git/hooks while it is set,"
	echo "so nothing was installed. Add these lines to the matching hooks there:"
	for h in $hooks; do line "$h"; done
	exit 0
fi

git_hooks=$(git rev-parse --git-path hooks)
mkdir -p "$git_hooks"
git_hooks=$(cd "$git_hooks" && pwd -P)

pending=""
for h in $hooks; do
	target="$git_hooks/$h"
	if [ -e "$target" ] || [ -L "$target" ]; then
		if grep -q 'vier-augen' "$target" 2>/dev/null; then
			echo "$h: already installed."
		else
			echo "$h: $target exists and was left untouched."
			pending="$pending $h"
		fi
		continue
	fi
	printf '#!/bin/sh\n# vier-augen hook wrapper, written by install.sh\nexec sh "%s/%s" "$@"\n' \
		"$hooks_dir" "$h" > "$target"
	chmod +x "$target"
	echo "$h: installed."
done

if [ -n "$pending" ]; then
	echo "To run both, add these lines to the existing hooks:"
	for h in $pending; do line "$h"; done
fi
