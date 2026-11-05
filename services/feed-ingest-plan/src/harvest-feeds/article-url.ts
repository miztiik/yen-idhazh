/** Expose the shared resource normalization used by articles and offered links. */
export {
  InvalidArticleUrlError,
  normalizeResourceUrl as cleanArticleUrl,
  normalizeResourceUrlInput as normalizeArticleUrlInput,
} from "./normalize-resource-url";
