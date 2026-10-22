import { expect, mock, test } from "claude-code/testing";

const BAND = {
  plugin: "bdt-status",
  component: "AbovePrompt",
  surface: "terminal",
  viewport: { columns: 100, rows: 30 },
  props: {
    hasSurvey: false,
    isWorking: false,
    maxRows: 5,
    bodyColumns: 80,
    scroll: { offset: 0, bodyRows: 5 },
    view: {},
  },
} as const;

const INFO = {
  number: 69,
  title: "feat: mod",
  url: "https://github.com/bmsuisse/devtools/pull/69",
  state: "open",
  draft: false,
  build: "failing",
  issues: [
    { number: 68, url: "https://github.com/bmsuisse/devtools/issues/68" },
  ],
};

const SECOND = {
  number: 70,
  title: "feat: the same mod, into main",
  url: "https://github.com/bmsuisse/devtools/pull/70",
  state: "open",
  draft: true,
  build: "passing",
  issues: [],
};

// What a bdt without `--all` prints for it
const NO_ALL = {
  exitCode: 2,
  stdout: "",
  stderr: "│ No such option: --all (Possible options: --pat) │",
};

type Answer = { exitCode: number; stdout: string; stderr?: string };

// A bdt that knows `--all`: it answers with the list of PRs (`[]` for none, exit 0)
function all(...infos: object[]): Answer {
  return { exitCode: 0, stdout: JSON.stringify(infos) };
}

// Answers what Claude Code would: the session starts, `bdt pr info --json [--all]` is answered by `answer(argv)`,
// and the band has nothing of its own to draw
function stubSession(on, answer: (argv: readonly string[]) => Answer | "deny") {
  const clock = mock.clock(on);
  const calls: string[][] = [];
  on("session.start", () => ({ cwd: "/work" }));
  on("process.run", (_$, e) => {
    calls.push([...e.argv]);
    const a = answer(e.argv);
    if (a === "deny") return { deny: "bdt not found" };
    return { value: { stderr: "", ...a } };
  });
  on("ui.render", () => ({
    type: "Text",
    props: {},
    children: ["drawn by Claude Code"],
  }));
  return { clock, calls };
}

async function start($, clock) {
  await $.session.start({
    surface: "terminal",
    isInteractive: true,
    cwd: "/work",
  });
  await clock.settle();
}

test("links the PR with its title, the issue it closes and the build state", async ($, on) => {
  const { clock, calls } = stubSession(on, () => all(INFO));
  await start($, clock);

  const ui = await $.ui.mount(BAND);
  expect(calls[0]).toEqual(["bdt", "pr", "info", "--json", "--all"]);
  expect((await ui.find({ type: "Link", text: "PR #69" }))?.props.href).toBe(
    INFO.url,
  );
  expect(await ui.find({ type: "Text", text: "feat: mod" })).toBeDefined();
  expect((await ui.find({ type: "Link", text: "#68" }))?.props.href).toBe(
    INFO.issues[0].url,
  );
  expect(await ui.find({ type: "Text", text: /failing/ })).toBeDefined();
  // What Claude Code draws in the band is kept
  expect(
    await ui.find({ type: "Text", text: "drawn by Claude Code" }),
  ).toBeDefined();
});

test("shows every PR of the branch, one row each", async ($, on) => {
  const { clock } = stubSession(on, () => all(INFO, SECOND));
  await start($, clock);

  const ui = await $.ui.mount(BAND);
  expect((await ui.find({ type: "Link", text: "PR #69" }))?.props.href).toBe(
    INFO.url,
  );
  expect((await ui.find({ type: "Link", text: "PR #70" }))?.props.href).toBe(
    SECOND.url,
  );
  expect(
    await ui.find({ type: "Text", text: "feat: the same mod, into main" }),
  ).toBeDefined();
  expect(await ui.find({ type: "Text", text: "draft" })).toBeDefined();
  expect(
    await ui.find({ type: "Text", text: "drawn by Claude Code" }),
  ).toBeDefined();
});

test("cuts a long title to 50 characters, ending in an ellipsis", async ($, on) => {
  const title = "x".repeat(49) + "yz";
  const { clock } = stubSession(on, () => all({ ...INFO, title }));
  await start($, clock);

  const ui = await $.ui.mount(BAND);
  expect(
    await ui.find({ type: "Text", text: "x".repeat(49) + "…" }),
  ).toBeDefined();
  expect(await ui.find({ type: "Text", text: /yz/ })).toBeUndefined();
});

test("keeps a title of exactly 50 characters whole", async ($, on) => {
  const title = "y".repeat(50);
  const { clock } = stubSession(on, () => all({ ...INFO, title }));
  await start($, clock);

  const ui = await $.ui.mount(BAND);
  expect(await ui.find({ type: "Text", text: title })).toBeDefined();
});

test("falls back to the single PR when bdt does not know --all, and stops asking for it", async ($, on) => {
  const { clock, calls } = stubSession(on, (argv) =>
    argv.includes("--all")
      ? NO_ALL
      : { exitCode: 0, stdout: JSON.stringify(INFO) },
  );
  await start($, clock);
  await clock.advance(30_000);

  const ui = await $.ui.mount(BAND);
  expect((await ui.find({ type: "Link", text: "PR #69" }))?.props.href).toBe(
    INFO.url,
  );
  expect(calls.filter((c) => c.includes("--all"))).toHaveLength(1);
  expect(calls.filter((c) => !c.includes("--all")).length).toBeGreaterThan(1);
});

test("draws nothing of its own when the branch has no PR", async ($, on) => {
  const { clock } = stubSession(on, () => all());
  await start($, clock);

  const ui = await $.ui.mount(BAND);
  expect(await ui.find({ type: "Link" })).toBeUndefined();
  expect(
    await ui.find({ type: "Text", text: "drawn by Claude Code" }),
  ).toBeDefined();
});

test("draws nothing of its own when an old bdt says there is no PR", async ($, on) => {
  const { clock } = stubSession(on, (argv) =>
    argv.includes("--all") ? NO_ALL : { exitCode: 1, stdout: "" },
  );
  await start($, clock);

  expect(await (await $.ui.mount(BAND)).find({ type: "Link" })).toBeUndefined();
});

test("ignores a single object where a list is expected, as from a shadowing bdt", async ($, on) => {
  const { clock } = stubSession(on, () => ({
    exitCode: 0,
    stdout: JSON.stringify(INFO),
  }));
  await start($, clock);

  expect(await (await $.ui.mount(BAND)).find({ type: "Link" })).toBeUndefined();
});

test("shows none of the list when one entry has a foreign link", async ($, on) => {
  const evil = { ...SECOND, url: "https://evil.example/pull/1" };
  const { clock } = stubSession(on, () => all(INFO, evil));
  await start($, clock);

  expect(await (await $.ui.mount(BAND)).find({ type: "Link" })).toBeUndefined();
});

test("picks up a PR that appears later, on the next refresh", async ($, on) => {
  let answer = all();
  const { clock } = stubSession(on, () => answer);
  await start($, clock);

  answer = all(INFO);
  await clock.advance(30_000);

  const ui = await $.ui.mount(BAND);
  expect((await ui.find({ type: "Link", text: "PR #69" }))?.props.href).toBe(
    INFO.url,
  );
});

test("keeps showing the last PRs when a refresh fails, and drops them when bdt says there are none", async ($, on) => {
  let answer: Answer | "deny" = all(INFO, SECOND);
  const { clock } = stubSession(on, () => answer);
  await start($, clock);

  answer = "deny";
  await clock.advance(30_000);
  expect(
    await (await $.ui.mount(BAND)).find({ type: "Link", text: "PR #70" }),
  ).toBeDefined();

  // a failure of a bdt that knows --all is not "no PR"
  answer = { exitCode: 1, stdout: "", stderr: "boom" };
  await clock.advance(30_000);
  expect(
    await (await $.ui.mount(BAND)).find({ type: "Link", text: "PR #69" }),
  ).toBeDefined();

  answer = all();
  await clock.advance(30_000);
  expect(await (await $.ui.mount(BAND)).find({ type: "Link" })).toBeUndefined();
});
