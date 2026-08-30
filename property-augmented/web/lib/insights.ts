import raw from'../content/insights.json';
export type Insight={slug:string;title:string;description:string;published:string;reviewed:string;tool:string;sections:{heading:string;body:string[]}[];sources:{name:string;url:string}[]};
export const insights=raw as Insight[];
export const insightMap=Object.fromEntries(insights.map(x=>[x.slug,x])) as Record<string,Insight>;
