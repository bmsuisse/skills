// Shows one row per open PR of the branch, e.g. "PR #69 feat: mod ✓ passing · closes #68" (clickable links), in the
// band above the prompt, from `bdt pr info --json --all`. An older `bdt` without `--all` gives its single PR.
// Needs `bdt` on PATH; with no PR for the current branch (or no bdt) the band is left alone.

const REFRESH_MS = 30_000;

// Single-width symbols, not emoji, so the band lines up in every terminal
const BUILD = {
  passing: { symbol: "✓", color: "green" },
  failing: { symbol: "✗", color: "red" },
  pending: { symbol: "…", color: "yellow" },
  waiting: { symbol: "⏸", color: "yellow" },
};

const MAX_TITLE = 50;

// The last answer: the branch's PRs, `[]` when it has none
let prs = [];
// Cleared once `bdt` says it doesn't know `--all`, so an old bdt isn't asked twice per refresh
let hasAll = true;
let isRefreshing = false;
let timer = null;

const LINK = /^https:\/\/(github\.com|dev\.azure\.com)\/[^\s\x00-\x1f]*$/;

// `bdt` output only if it has the shape `bdt pr info --json` produces, so a shadowing or outdated `bdt` on PATH
// can't make the band render an arbitrary link
function validated(i) {
  const isLink = (x) =>
    typeof x?.number === "number" &&
    typeof x.url === "string" &&
    LINK.test(x.url);
  return isLink(i) && Array.isArray(i.issues) && i.issues.every(isLink)
    ? i
    : undefined;
}

// At most `MAX_TITLE` characters, ending in an ellipsis when cut; `bdt` already strips control characters
function shortTitle(title) {
  if (typeof title !== "string") return "";
  const chars = [...title.trim()];
  return chars.length > MAX_TITLE
    ? chars
        .slice(0, MAX_TITLE - 1)
        .join("")
        .trimEnd() + "…"
    : chars.join("");
}

async function runInfo($, args) {
  const r = await $.process.run(["bdt", "pr", "info", "--json", ...args]);
  return { ...r, output: `${r.stdout}\n${r.stderr ?? ""}` };
}

// `undefined`: couldn't ask (bdt missing or timed out, unusable output) -- keep showing the last answer.
// `[]`: bdt answered that there is no PR for this branch.
async function readPrs($) {
  try {
    if (hasAll) {
      const r = await runInfo($, ["--all"]);
      if (r.exitCode === 0) {
        const list = JSON.parse(r.stdout);
        if (!Array.isArray(list)) return undefined;
        const valid = list.map(validated);
        return valid.every(Boolean) ? valid : undefined;
      }
      // Unlike without `--all`, a failure is not "no PR": that is `[]` with exit 0
      if (!/no such option/i.test(r.output)) return undefined;
      hasAll = false;
    }
    const r = await runInfo($, []);
    if (r.exitCode !== 0) return [];
    const one = validated(JSON.parse(r.stdout));
    return one ? [one] : undefined;
  } catch {
    return undefined;
  }
}

async function refresh($) {
  // A slow `gh` call must not stack up behind the timer
  if (isRefreshing) return;
  isRefreshing = true;
  try {
    const next = await readPrs($);
    if (next !== undefined && JSON.stringify(next) !== JSON.stringify(prs)) {
      prs = next;
      $.ui.invalidate("ui.render");
    }
  } catch {
    // a failed redraw must not become an unhandled rejection in a timer callback
  } finally {
    isRefreshing = false;
  }
}

export function register(on) {
  on("session.start", async ($, e, next) => {
    // once per module load, not per session.start
    timer ??= $.clock.every(REFRESH_MS, () => refresh($));
    // Not awaited: the session starts right away, and the band fills in when bdt answers
    refresh($);
    return next(e);
  });

  // A turn is when the branch is most likely to have been pushed or a PR opened
  on("turn.complete", async ($, e, next) => {
    refresh($);
    return next(e);
  });

  on("ui.render", { component: "AbovePrompt" }, async ($, e, next) => {
    // Keep whatever Claude Code or other mods draw in the band
    const theirs = await next(e);
    if (prs.length === 0) return theirs;

    const { Box, Text, Link } = $.ui.resolve(e);
    const rows = prs.map((info) => {
      const build = BUILD[info.build];
      const state = info.draft
        ? "draft"
        : info.state === "open"
          ? ""
          : info.state;
      const title = shortTitle(info.title);

      return Box({
        flexDirection: "row",
        columnGap: 1,
        children: [
          Link({ href: info.url, label: "PR #" + info.number }),
          ...(title ? [Text({ children: [title] })] : []),
          ...(build
            ? [
                Text({
                  color: build.color,
                  children: [build.symbol + " " + info.build],
                }),
              ]
            : []),
          ...(state ? [Text({ dimColor: true, children: [state] })] : []),
          ...info.issues.flatMap((issue) => [
            Text({ dimColor: true, children: ["· closes"] }),
            Link({ href: issue.url, label: "#" + issue.number }),
          ]),
        ],
      });
    });

    return Box({
      flexDirection: "column",
      children: theirs ? [...rows, theirs] : rows,
    });
  });
}
