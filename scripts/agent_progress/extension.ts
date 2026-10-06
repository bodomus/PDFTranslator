import { Type } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { appendProgress } from "./journal.mjs";

export default function (pi: ExtensionAPI) {
  pi.registerFlag("progress-ticket", { description: "Runner-bound progress ticket", type: "string" });
  pi.registerFlag("progress-role", { description: "Runner-bound progress role", type: "string" });
  let root: string;
  let ticket: string;
  let role: string;
  pi.on("session_start", (_event, ctx) => {
    root = ctx.cwd;
    ticket = String(pi.getFlag("progress-ticket") ?? "");
    role = String(pi.getFlag("progress-role") ?? "");
  });
  pi.registerTool({
    name: "progress_append",
    label: "Operational milestone",
    description: "Append one short factual milestone to your runner-bound journal (UTC). No reasoning, secrets, URLs or arbitrary paths. Only major steps, test results or blockers; not periodic heartbeats.",
    parameters: Type.Object({ message: Type.String({ minLength: 1, maxLength: 240 }) }, { additionalProperties: false }),
    async execute(_id, params) {
      if (!root) throw new Error("Progress binding unavailable");
      appendProgress(root, ticket, role, params);
      return { content: [{ type: "text", text: "Recorded" }], details: undefined };
    },
  });
}
