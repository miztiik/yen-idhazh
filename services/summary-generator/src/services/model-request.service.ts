// Build a chat request and read its answer without guessing model-specific syntax.
import type { ModelRuntime } from "../config/load-model-runtime.js";

// These keys are owned by this application's turn assembly and decoding, not native tunables.
const MODEL_REQUEST_CONTROL_KEYS = ["messages", "response_format"] as const;

export function rejectModelRequestControls(request: Record<string, unknown>): void {
  for (const key of MODEL_REQUEST_CONTROL_KEYS) {
    if (key in request) throw new Error(`Selected model sampling may not set ${key}; the caller sets it.`);
  }
}

export function buildModelRequest(
  runtime: ModelRuntime,
  systemPrompt: string,
  userPrompt: string,
  responseFormat: Record<string, unknown>,
) {
  const controls = {
    messages: [
      { role: "system", content: systemPrompt },
      { role: "user", content: userPrompt },
    ],
    response_format: responseFormat,
  };
  rejectModelRequestControls(runtime.request);
  return { ...runtime.request, ...controls };
}

export function readModelContent(
  response: { choices?: { message?: { content?: string | null; reasoning_content?: string | null } }[] },
  runtime: Pick<ModelRuntime, "reasoning_delimiters">,
): string {
  const message = response.choices?.[0]?.message;
  const content = message?.content ?? "";
  if (typeof message?.reasoning_content === "string" && message.reasoning_content.length > 0) {
    return content;
  }
  const delimiters = runtime.reasoning_delimiters;
  if (delimiters === null) {
    return content;
  }
  const [opening, closing] = delimiters;
  let answer = content.trimStart();
  let removed = false;
  while (answer.startsWith(opening)) {
    const end = answer.indexOf(closing, opening.length);
    if (end < 0) {
      throw new Error("The model returned an unfinished reasoning block.");
    }
    answer = answer.slice(end + closing.length).trimStart();
    removed = true;
  }
  return removed ? answer : content;
}
