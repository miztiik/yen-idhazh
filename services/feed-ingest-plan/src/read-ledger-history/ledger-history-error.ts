/** Which rejected native history data can a caller report without using its rows? */
export class LedgerHistoryReadError extends Error {
  override readonly name = "LedgerHistoryReadError";
}
