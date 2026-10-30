export const pageHead = (title: string, description: string) => ({ meta: [
  { title: `${title} | EHDS Navigator` }, { name: "description", content: description },
  { property: "og:title", content: `${title} | EHDS Navigator` }, { property: "og:description", content: description },
  { property: "og:type", content: "website" }, { name: "twitter:card", content: "summary_large_image" },
] });