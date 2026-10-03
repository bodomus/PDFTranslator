// Trusted implementation, NOT a generic Git or subprocess tool.
import { execFile } from "node:child_process";
import { lstatSync, statSync, realpathSync, existsSync, readdirSync } from "node:fs";
import { delimiter, isAbsolute, join, relative, sep } from "node:path";

export const OPERATIONS = ["status", "head", "resolve_revision", "diff", "show", "merge_base", "log", "current_branch", "working_diff"];
const MAX_BYTES = 4 * 1024 * 1024;
const TIMEOUT_MS = 30000;

function revision(value) {
  if (typeof value !== "string" || !/^(HEAD|[a-fA-F0-9]{40}|[a-fA-F0-9]{64})$/.test(value)) {
    throw new Error("revision must be HEAD or a full hexadecimal commit ID");
  }
  return value;
}

function environment() {
  // Retain OS process essentials, not Git routing/config/trace/helper variables.
  const env = Object.fromEntries(Object.entries(process.env).filter(([key]) => !key.toUpperCase().startsWith("GIT_")));
  return { ...env,
    GIT_OPTIONAL_LOCKS: "0", GIT_NO_REPLACE_OBJECTS: "1", GIT_NO_LAZY_FETCH: "1", GIT_TERMINAL_PROMPT: "0", GIT_PAGER: "", GIT_EXTERNAL_DIFF: "" };
}

function gitExecutable(root) {
  // An absolute executable prevents Windows/current-directory or relative-PATH hijacking.
  const pathValue = Object.entries(process.env).find(([key]) => key.toUpperCase() === "PATH")?.[1] ?? "";
  for (const directory of pathValue.split(delimiter)) {
    if (!isAbsolute(directory)) continue;
    const candidate = join(directory, process.platform === "win32" ? "git.exe" : "git");
    if (!existsSync(candidate) || !statSync(candidate).isFile()) continue;
    const actual = realpathSync(candidate);
    const location = relative(root, actual);
    if (location === "" || (!location.startsWith(`..${sep}`) && location !== ".." && !isAbsolute(location))) continue;
    return actual;
  }
  throw new Error("trusted Git executable not found on absolute PATH outside repository");
}

export class GitReadonlyInspector {
  constructor(root) {
    this.root = realpathSync(root);
    this.gitDir = join(this.root, ".git");
    this.executable = gitExecutable(this.root);
    if (!lstatSync(this.gitDir).isDirectory() || realpathSync(this.gitDir) !== this.gitDir) {
      throw new Error("Git inspection requires an in-root physical .git directory (no gitfiles/symlinks)");
    }
    // Alternate object stores escape the root; partial clones may invoke implicit transport.
    if (existsSync(join(this.gitDir, "objects", "info", "alternates")) ||
        existsSync(join(this.gitDir, "objects", "info", "http-alternates")) ||
        readdirSync(join(this.gitDir, "objects", "pack")).some(name => name.endsWith(".promisor"))) {
      throw new Error("alternate object stores and partial clones are unsupported");
    }
  }

  async #run(args, signal, hardening = []) {
    const nullPath = process.platform === "win32" ? "NUL" : "/dev/null";
    const fixed = ["--no-pager", `--git-dir=${this.gitDir}`, `--work-tree=${this.root}`,
      "-c", "core.fsmonitor=false", "-c", `core.hooksPath=${nullPath}`,
      "-c", "core.untrackedCache=false", "-c", "core.preloadIndex=false",
      "-c", "diff.external=", "-c", "diff.ignoreSubmodules=all",
      "-c", "submodule.recurse=false", "-c", "protocol.allow=never",
      "-c", "credential.helper=", "-c", "core.quotePath=true", "-c", "color.ui=false"];
    return new Promise((resolve, reject) => {
      execFile(this.executable, [...fixed, ...hardening, ...args], { cwd: this.root, env: environment(), shell: false,
        encoding: "utf8", maxBuffer: MAX_BYTES, timeout: TIMEOUT_MS, signal, windowsHide: true },
      (error, stdout, stderr) => {
        if (error) reject(new Error(`Git inspection failed (timeout/output limit/errors fail closed): ${error.message}; ${stderr.slice(0, 2000)}`));
        else resolve(stdout);
      });
    });
  }

  async #resolve(value, signal, hardening = []) {
    const sha = (await this.#run(["rev-parse", "--verify", "--end-of-options", `${revision(value)}^{commit}`], signal, hardening)).trim();
    revision(sha);
    return sha;
  }

  async query(input, signal) {
    if (!input || typeof input !== "object" || Array.isArray(input) || !OPERATIONS.includes(input.operation)) {
      throw new Error("unsupported Git read-only operation");
    }
    const fields = { status: [], head: [], current_branch: [], resolve_revision: ["revision"],
      working_diff: ["staged"], show: ["commit"], diff: ["base", "head"], merge_base: ["base", "head"], log: ["base", "head", "limit"] }[input.operation];
    if (Object.keys(input).some(key => key !== "operation" && !fields.includes(key)) ||
        fields.some(key => !(key in input))) throw new Error("unexpected or missing operation arguments");
    if (input.operation === "log" && (!Number.isInteger(input.limit) || input.limit < 1 || input.limit > 100)) {
      throw new Error("log limit must be an integer from 1 to 100");
    }
    if (input.operation === "working_diff" && typeof input.staged !== "boolean") {
      throw new Error("working_diff requires a boolean staged argument");
    }
    // Validate all supplied revisions BEFORE invoking any process.
    for (const field of fields.filter(key => key !== "limit" && key !== "staged")) revision(input[field]);
    // Older Git may ignore GIT_NO_LAZY_FETCH; reject promisor configuration as well.
    const config = await this.#run(["config", "--null", "--list"], signal);
    const entries = config.split("\0").map(entry => entry.split("\n", 2));
    if (entries.some(([key, value]) => key === "extensions.partialclone" ||
        (/^remote\..*\.promisor$/i.test(key) && /^(true|1|yes|on)?$/i.test(value ?? "")))) {
      throw new Error("partial clone configuration is unsupported");
    }
    // Status/diff may run clean/process filters while hashing work-tree files!
    // Neutralize every configured driver, not just external diff/textconv.
    const keys = (await this.#run(["config", "--null", "--name-only", "--list"], signal)).split("\0");
    const drivers = new Set();
    for (const key of keys.filter(key => /^filter\./i.test(key))) {
      const match = /^filter\.([A-Za-z0-9_-]+)\.[A-Za-z0-9-]+$/.exec(key);
      if (!match) throw new Error("unsupported filter configuration name; fail closed");
      drivers.add(match[1]);
    }
    const hardening = [...drivers].flatMap(driver => ["-c", `filter.${driver}.clean=`, "-c", `filter.${driver}.smudge=`,
      "-c", `filter.${driver}.process=`, "-c", `filter.${driver}.required=false`]);
    const run = args => this.#run(args, signal, hardening);
    const resolve = value => this.#resolve(value, signal, hardening);
    const patch = ["--no-ext-diff", "--no-textconv", "--ignore-submodules=all", "--no-color"];
    switch (input.operation) {
      case "status": return run(["status", "--porcelain=v1", "--untracked-files=all", "--ignore-submodules=all"]);
      case "working_diff": return run(["diff", ...patch, ...(input.staged ? ["--cached"] : []), "--"]);
      case "head": return resolve("HEAD");
      case "resolve_revision": return resolve(input.revision);
      case "current_branch": return run(["branch", "--show-current"]);
      case "show": return run(["show", ...patch, "--no-show-signature", "--format=fuller", "--stat", "--patch", await resolve(input.commit), "--"]);
      default: {
        const base = await resolve(input.base);
        const head = await resolve(input.head);
        if (input.operation === "diff") return run(["diff", ...patch, base, head, "--"]);
        if (input.operation === "merge_base") return run(["merge-base", base, head]);
        return run(["log", "--no-decorate", "--no-show-signature", `--max-count=${input.limit}`,
          "--format=%H %P %s", `${base}..${head}`, "--"]);
      }
    }
  }
}
