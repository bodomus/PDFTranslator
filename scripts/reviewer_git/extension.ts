import { Type } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { GitReadonlyInspector, OPERATIONS } from "./inspector.mjs";

// Root comes only from runner-bound cwd, never from tool parameters.
export default function (pi: ExtensionAPI) {
  let inspector: GitReadonlyInspector;
  pi.on("session_start", (_event, ctx) => {
    inspector = new GitReadonlyInspector(ctx.cwd);
  });
  pi.registerTool({
    name: "git_readonly",
    label: "Git read-only inspection",
    description: "Constrained local Git evidence, not shell access. Operations: status, head, current_branch; resolve_revision(revision); show(commit); diff/merge_base(base,head); log(base,head,limit 1..100); working_diff(staged boolean). Revisions: HEAD or full SHA only. Diff compares endpoints; query merge_base first for merge-base semantics. Errors fail closed; output capped at 4 MiB and 30 seconds.",
    parameters: Type.Object({
      operation: Type.Union(OPERATIONS.map(operation => Type.Literal(operation))),
      revision: Type.Optional(Type.String()), commit: Type.Optional(Type.String()),
      base: Type.Optional(Type.String()), head: Type.Optional(Type.String()),
      limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 100 })),
      staged: Type.Optional(Type.Boolean()),
    }, { additionalProperties: false }),
    async execute(_id, params, signal) {
      if (!inspector) throw new Error("Git inspector did not initialize; fail closed");
      const text = await inspector.query(params, signal);
      return { content: [{ type: "text", text }], details: undefined };
    },
  });
  // Enforce at runtime as well as CLI, regardless of provider/model.
  pi.on("tool_call", event => {
    if (!["read", "grep", "find", "ls", "git_readonly"].includes(event.toolName)) {
      return { block: true, reason: "Reviewer capability is read-only; no shell or writes" };
    }
  });
}
