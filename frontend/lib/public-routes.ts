export function publicNovelHref(slug: string): string {
  return `/novels/${encodeURIComponent(slug)}`;
}

export function publicChapterHref(slug: string, chapterId: string): string {
  return `${publicNovelHref(slug)}/chapter/${encodeURIComponent(chapterId)}`;
}
