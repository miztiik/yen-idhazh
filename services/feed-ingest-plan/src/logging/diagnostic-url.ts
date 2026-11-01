/** Remove credentials, query values and fragments from diagnostic addresses. */
export function diagnosticUrl(value: string): string | undefined {
  try {
    const url = new URL(value);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) return undefined;
    if ([...url.searchParams.keys()].some(key => /token|secret|signature|credential|authorization|key|auth|sig/i.test(key))) return undefined;
    url.search = "";
    url.hash = "";
    return url.href.length <= 512 ? url.href : undefined;
  } catch (error) {
    if (!(error instanceof TypeError)) throw error;
    return undefined;
  }
}
