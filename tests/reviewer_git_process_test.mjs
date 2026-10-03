// No provider/Pi dependency. Inspect the actual process boundary and cancellation.
import assert from "node:assert/strict";
import childProcess from "node:child_process";
import { syncBuiltinESMExports } from "node:module";
import { isAbsolute, basename } from "node:path";

const calls = [];
childProcess.execFile = (binary, args, options, callback) => {
  calls.push({ binary, args, options });
  callback(null, args.includes("config") ? "core.autocrlf\ntrue\0" : "", "");
};
syncBuiltinESMExports();
const { GitReadonlyInspector } = await import("../scripts/reviewer_git/inspector.mjs");
const inspector = new GitReadonlyInspector(process.argv[2]);
await assert.rejects(inspector.query({operation: "add"}));
await assert.rejects(inspector.query({operation: "diff", base: "HEAD", head: "HEAD; escape"}));
assert.equal(calls.length, 0, "bad input reached subprocess");
await inspector.query({operation: "status"});
assert.equal(calls.length, 3);
for (const call of calls) {
  assert.ok(isAbsolute(call.binary));
  assert.match(basename(call.binary), /^git(?:\.exe)?$/i);
  assert.equal(call.options.shell, false);
  assert.equal(call.options.maxBuffer, 4 * 1024 * 1024);
  assert.equal(call.options.timeout, 30000);
  assert.equal(call.options.env.GIT_OPTIONAL_LOCKS, "0");
  assert.equal(call.options.env.GIT_NO_LAZY_FETCH, "1");
  assert.equal(call.options.env.GIT_NO_REPLACE_OBJECTS, "1");
  assert.ok(call.args.includes("--no-pager"));
  assert.ok(call.args.includes("protocol.allow=never"));
  assert.ok(call.args.includes("core.fsmonitor=false"));
  assert.ok(call.args.includes("submodule.recurse=false"));
  assert.equal(call.options.cwd, inspector.root);
}
const controller = new AbortController();
controller.abort();
await inspector.query({operation: "status"}, controller.signal);
assert.equal(calls.at(-1).options.signal, controller.signal);
console.log("process policy PASS");
