// Shows "PR #69 ✓ · closes #68" (clickable links) in the band above the prompt, from `bdt pr info --json`.
// Needs `bdt` on PATH; with no PR for the current branch (or no bdt) the band is left alone.

const REFRESH_MS = 30_000;

// Single-width symbols, not emoji, so the band lines up in every terminal
const BUILD = {
  passing: { symbol: "✓", color: "green" },
  failing: { symbol: "✗", color: "red" },
  pending: { symbol: "…", color: "yellow" },
  waiting: { symbol: "⏸", color: "yellow" },
};

// The last `bdt pr info --json` result, or null when the branch has no PR
let info = null;
let isRefreshing = false;
let timer = null;

const LINK = /^https:\/\/(github\.com|dev\.azure\.com)\/[^\s\x00-\x1f]*$/;

// `bdt` output only if it has the shape `bdt pr info --json` produces, so a shadowing or outdated `bdt` on PATH
// can't make the band render an arbitrary link
function validated(i) {
  const isLink = (x) =>
    typeof x.number === "number" &&
    typeof x.url === "string" &&
    LINK.test(x.url);
  return isLink(i) && Array.isArray(i.issues) && i.issues.every(isLink)
    ? i
    : undefined;
}

// `undefined`: couldn't ask (bdt missing or timed out, unusable output) -- keep showing the last answer.
// `null`: bdt answered that there is no PR for this branch.
async function readInfo($) {
  try {
    const r = await $.process.run(["bdt", "pr", "info", "--json"]);
    return r.exitCode === 0 ? validated(JSON.parse(r.stdout)) : null;
  } catch {
    return undefined;
  }
}

async function refresh($) {
  // A slow `gh` call must not stack up behind the timer
  if (isRefreshing) return;
  isRefreshing = true;
  try {
    const next = await readInfo($);
    if (next !== undefined && JSON.stringify(next) !== JSON.stringify(info)) {
      info = next;
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
    if (!info) return theirs;

    const { Box, Text, Link } = $.ui.resolve(e);
    const build = BUILD[info.build];
    const state = info.draft
      ? "draft"
      : info.state === "open"
        ? ""
        : info.state;

    const line = Box({
      flexDirection: "row",
      columnGap: 1,
      children: [
        Link({ href: info.url, label: "PR #" + info.number }),
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

    return Box({
      flexDirection: "column",
      children: theirs ? [line, theirs] : [line],
    });
  });
}
