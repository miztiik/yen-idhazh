/** How does a native caller preserve its own coded failures through shared process cleanup? */
export type HttpChildKind = "PLANNER" | "SAFE_PERSIST" | "TYPESCRIPT_API";
export interface HttpChildFailure extends Error { readonly code: string }

export type HttpChildFailurePolicy<Failure extends HttpChildFailure = HttpChildFailure> = {
  create: (code: string, message: string, cause?: unknown) => Failure;
  capture: (error: unknown, cancelled?: boolean) => Failure;
  retainCleanup: (error: Failure, close: () => unknown | Promise<unknown>) => Promise<Failure>;
  startup: (error: unknown, kind: HttpChildKind) => { error: Failure; packet: object };
  describe: (error: unknown) => object;
};
