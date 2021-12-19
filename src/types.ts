export interface Category {
  name: string;
  tags: string[];
  color: string;
}

export interface PlotHTMLElement extends HTMLElement {
  on(eventName: string, handler: Function): void;
}
