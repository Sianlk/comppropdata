import raw from'../content/book.json';
export type BookSection={heading:string;body:string[]};
export type BookChapter={slug:string;number:number;title:string;standfirst:string;sections:BookSection[]};
export type BookSource={name:string;url:string};
export const book=raw as typeof raw&{chapters:BookChapter[];sources:BookSource[]};
export const chapters=book.chapters as BookChapter[];
export const chapterMap=Object.fromEntries(chapters.map(c=>[c.slug,c])) as Record<string,BookChapter>;
