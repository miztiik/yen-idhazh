/** Clean a request address without changing the offered article's persisted identity. */
import { TidyCleaner } from "tidy-url";
import { UnsafeTargetError, validateTargetName } from "./safe-target";

export function cleanHttpRequestTarget(raw: string): URL {
  const offered = validateTargetName(raw);
  const cleaner = new TidyCleaner();
  // This pinned release suppresses console output when silent is false.
  cleaner.config.silent = false;
  let target: string;
  try { target = cleaner.clean(offered.href).url; }
  catch (error) {
    if (error instanceof TypeError || error instanceof URIError) throw new UnsafeTargetError();
    throw error;
  }
  return validateTargetName(target);
}
