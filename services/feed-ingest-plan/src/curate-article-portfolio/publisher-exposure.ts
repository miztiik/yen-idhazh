/** Which genuine UTC-day publication counts have a confirmed recorded publisher? */
export type PublisherPublicationHistory = Readonly<{
  day: string; availability: "available" | "unavailable"; counts: ReadonlyMap<string, number>;
}>;
