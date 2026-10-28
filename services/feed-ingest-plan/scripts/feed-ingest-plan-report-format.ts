/** How are reusable report notices written as workflow annotations? */
import type { PlannerMarkdownNotice } from "../src/reporting";

export function escapeCommand(value: string): string {
  return value.replaceAll("%", "%25").replaceAll("\r", "%0D").replaceAll("\n", "%0A");
}

export function escapeParameter(value: string): string {
  return escapeCommand(value).replaceAll(":", "%3A").replaceAll(",", "%2C");
}

export function formatWorkflowAnnotation(notice: PlannerMarkdownNotice): string {
  const command = notice.level === "warning" ? "warning" : "notice";
  return `::${command} title=${escapeParameter(notice.title)}::${escapeCommand(
    `${notice.message} Full details are in the public job summary.`,
  )}`;
}
