import { expect, test } from "bun:test";
import { resolveArticleEvidence, websiteGroup } from "../src/website-group";

test("website groups use registrable public and private suffixes across subdomains", () => {
  expect(websiteGroup("https://desk.news.example.co.uk/story", true)).toBe("example.co.uk");
  expect(websiteGroup("https://wire.example.co.uk/another-story", true)).toBe("example.co.uk");
  expect(websiteGroup("https://desk.publisher.github.io/story", true)).toBe("publisher.github.io");
  expect(websiteGroup("https://desk.publisher.github.io/story", false)).toBe("github.io");
});

test("canonical article URLs override supplied website-group hints", () => {
  const resolved = resolveArticleEvidence(
    { canonical_url: "https://section.publisher.example.co.uk/story", word_count: 21 },
    { website_group: { value: "caller.example", origin: "caller" }, estimated_work: 34 },
    true,
  );
  expect(resolved).toEqual({
    website_group: { value: "example.co.uk", origin: "canonical_url" },
    estimated_work: 34,
  });
});
