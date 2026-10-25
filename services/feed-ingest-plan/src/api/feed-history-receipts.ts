/** Which durable native feed receipts must one listener retain between planning requests? */
import type { PlanInputs } from "../load-plan-inputs";
import { OwnFeedReceiptSchema } from "../read-ledger-history/own-feed-receipts";
import type { FeedWriteReceipt, OwnFeedReceipt } from "../read-ledger-history/own-feed-receipts";

export function retainFeedReceipts(inputs: PlanInputs, initial: readonly OwnFeedReceipt[] = []) {
  const health = new Map<string, Set<string>>();
  const retainedDays = Math.max(
    inputs.harvest.config.feedback.lifecycle_window_days,
    inputs.clock_config.collect.reliability_window_days,
  );
  const add = (raw: OwnFeedReceipt) => {
    const receipt = OwnFeedReceiptSchema.parse(raw);
    const paths = health.get(receipt.day) ?? new Set<string>();
    for (const path of receipt.files) paths.add(path);
    health.set(receipt.day, paths);
    for (const day of [...health.keys()].sort().slice(0, -retainedDays)) health.delete(day);
  };
  initial.forEach(add);
  return {
    remember(receipt: FeedWriteReceipt) {
      if (receipt.files.length === 0) return;
      const files = receipt.files.map(file => file.path);
      add({ ledger: receipt.ledger, day: receipt.day, files });
    },
    read(): OwnFeedReceipt[] {
      return [
        ...[...health].sort(([a], [b]) => a.localeCompare(b))
          .map(([day, files]) => ({ ledger: "feed-health" as const, day, files: [...files] })),
      ];
    },
  };
}
