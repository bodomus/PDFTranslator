import fs from "node:fs";
import path from "node:path";

// No caller-supplied file path. No shell, subprocess, truncation or arbitrary write.
export function appendProgress(root, ticket, role, params, now = new Date()) {
  if (!/^[A-Z][A-Z0-9]*-[1-9][0-9]*[A-Z]*$/.test(ticket) || !["implementer", "reviewer"].includes(role)) {
    throw new Error("Invalid runner progress binding");
  }
  if (!params || Object.keys(params).length !== 1 || typeof params.message !== "string") {
    throw new Error("Progress accepts only a message");
  }
  const message = params.message.trim();
  if (!message || message.length > 240 || /[\p{C}\r\n]/u.test(message)) {
    throw new Error("Progress requires one short printable line (1..240 characters)");
  }
  // Defense in depth, not a credential detector: instructions forbid all sensitive content.
  if (/https?:\/\/|authorization|bearer\s|password|oauth|api[_ -]?key|access[_ -]?token|sk-[a-z0-9]|gh[pousr]_/i.test(message)) {
    throw new Error("Summarize external failures without URLs or credentials");
  }
  const base = fs.realpathSync(root);
  const directory = path.join(base, ".agent-cycle", ticket);
  for (const location of [path.dirname(directory), directory]) {
    if (fs.lstatSync(location).isSymbolicLink() || fs.realpathSync(location) !== location) {
      throw new Error("Redirected progress directory is unsupported");
    }
  }
  const target = path.join(directory, `${role}-progress.log`);
  if (fs.existsSync(target)) {
    const stat = fs.lstatSync(target);
    if (!stat.isFile() || stat.isSymbolicLink() || stat.nlink !== 1) {
      throw new Error("Redirected progress journal is unsupported");
    }
  }
  const fd = fs.openSync(target, fs.constants.O_WRONLY | fs.constants.O_APPEND | fs.constants.O_CREAT | (fs.constants.O_NOFOLLOW || 0), 0o600);
  try {
    if (!fs.fstatSync(fd).isFile() || fs.fstatSync(fd).nlink !== 1) throw new Error("Invalid journal");
    const timestamp = now.toISOString().slice(11, 16);
    fs.writeSync(fd, `[${timestamp}] ${message}\n`);
  } finally {
    fs.closeSync(fd);
  }
}
