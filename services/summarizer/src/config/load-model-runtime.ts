// Load the selected request declaration through the existing Python validator.
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "zod";

const repositoryRoot = fileURLToPath(new URL("../../../../", import.meta.url));

const ModelRuntimeSchema = z.object({
  base_url: z.string().url(),
  request: z.object({
    model: z.string().min(1),
    stream: z.literal(false),
    chat_template_kwargs: z.record(z.unknown()).optional(),
  }).passthrough(),
  reasoning_delimiters: z.tuple([z.string().min(1), z.string().min(1)]).nullable(),
  timeout_seconds: z.number().positive().finite(),
  repo: z.string().min(1),
  file: z.string().min(1),
});

export type ModelRuntime = z.infer<typeof ModelRuntimeSchema>;

export function loadModelRuntime(configRoot = path.join(repositoryRoot, "config")): ModelRuntime {
  const localPython = path.join(
    repositoryRoot, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
  );
  const python = existsSync(localPython) ? localPython : "python";
  const output = execFileSync(
    python,
    [
      path.join(repositoryRoot, "backend", "utilities", "model_runtime.py"),
      "describe-request",
      "--config-root",
      path.resolve(configRoot),
    ],
    {
      cwd: repositoryRoot,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
      env: {
        ...process.env,
        PYTHONPATH: [path.join(repositoryRoot, "backend"), process.env.PYTHONPATH]
          .filter(Boolean).join(path.delimiter),
      },
    },
  );
  return ModelRuntimeSchema.parse(JSON.parse(output));
}
