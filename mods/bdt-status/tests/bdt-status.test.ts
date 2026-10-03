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

// Answers what Claude Code would: the session starts, `bdt pr info --json` prints `stdout` (exit `exitCode`),
// and the band has nothing of its own to draw
function stubSession(on, exitCode: number, stdout: string) {
  const clock = mock.clock(on);
  on("session.start", () => ({ cwd: "/work" }));
  on("process.run", () => ({ value: { exitCode, stdout, stderr: "" } }));
  on("ui.render", () => ({
    type: "Text",
    props: {},
    children: ["drawn by Claude Code"],
  }));
  return clock;
}

test("links the PR and the issue it closes, with the build state", async ($, on) => {
  const clock = stubSession(on, 0, JSON.stringify(INFO));
  await $.session.start({
    surface: "terminal",
    isInteractive: true,
    cwd: "/work",
  });
  await clock.settle();

  const ui = await $.ui.mount(BAND);
  expect((await ui.find({ type: "Link", text: "PR #69" }))?.props.href).toBe(
    INFO.url,
  );
  expect((await ui.find({ type: "Link", text: "#68" }))?.props.href).toBe(
    INFO.issues[0].url,
  );
  expect(await ui.find({ type: "Text", text: /failing/ })).toBeDefined();
  // What Claude Code draws in the band is kept
  expect(
    await ui.find({ type: "Text", text: "drawn by Claude Code" }),
  ).toBeDefined();
});

test("draws nothing of its own when the branch has no PR", async ($, on) => {
  const clock = stubSession(on, 1, "");
  await $.session.start({
    surface: "terminal",
    isInteractive: true,
    cwd: "/work",
  });
  await clock.settle();

  const ui = await $.ui.mount(BAND);
  expect(await ui.find({ type: "Link" })).toBeUndefined();
  expect(
    await ui.find({ type: "Text", text: "drawn by Claude Code" }),
  ).toBeDefined();
});

test("picks up a PR that appears later, on the next refresh", async ($, on) => {
  const clock = mock.clock(on);
  let stdout = "";
  on("session.start", () => ({ cwd: "/work" }));
  on("process.run", () => ({
    value: { exitCode: stdout ? 0 : 1, stdout, stderr: "" },
  }));
  on("ui.render", () => ({
    type: "Text",
    props: {},
    children: ["drawn by Claude Code"],
  }));
  await $.session.start({
    surface: "terminal",
    isInteractive: true,
    cwd: "/work",
  });
  await clock.settle();

  stdout = JSON.stringify(INFO);
  await clock.advance(30_000);

  const ui = await $.ui.mount(BAND);
  expect((await ui.find({ type: "Link", text: "PR #69" }))?.props.href).toBe(
    INFO.url,
  );
});

test("keeps showing the last PR when a refresh fails, and drops it when bdt says there is none", async ($, on) => {
  const clock = mock.clock(on);
  let answer: "pr" | "broken" | "no-pr" = "pr";
  on("session.start", () => ({ cwd: "/work" }));
  on("process.run", () => {
    if (answer === "broken") return { deny: "bdt not found" };
    return {
      value: {
        exitCode: answer === "pr" ? 0 : 1,
        stdout: answer === "pr" ? JSON.stringify(INFO) : "",
        stderr: "",
      },
    };
  });
  on("ui.render", () => ({
    type: "Text",
    props: {},
    children: ["drawn by Claude Code"],
  }));
  await $.session.start({
    surface: "terminal",
    isInteractive: true,
    cwd: "/work",
  });
  await clock.settle();

  answer = "broken";
  await clock.advance(30_000);
  expect(
    await (await $.ui.mount(BAND)).find({ type: "Link", text: "PR #69" }),
  ).toBeDefined();

  answer = "no-pr";
  await clock.advance(30_000);
  expect(await (await $.ui.mount(BAND)).find({ type: "Link" })).toBeUndefined();
});
