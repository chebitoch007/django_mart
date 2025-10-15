// HTMX type definitions
interface HTMXEventMap {
  'htmx:afterRequest': CustomEvent<{
    elt: HTMLElement;
    target: HTMLElement;
    requestConfig: any;
    xhr: XMLHttpRequest;
  }>;
  'htmx:beforeRequest': CustomEvent;
  'htmx:configRequest': CustomEvent;
  // Add other HTMX events as needed
}

declare global {
  interface Document {
    addEventListener<K extends keyof HTMXEventMap>(
      type: K,
      listener: (this: Document, ev: HTMXEventMap[K]) => void,
      options?: boolean | AddEventListenerOptions
    ): void;
    addEventListener(
      type: string,
      listener: EventListenerOrEventListenerObject,
      options?: boolean | AddEventListenerOptions
    ): void;
  }

  interface HTMLElement {
    addEventListener<K extends keyof HTMXEventMap>(
      type: K,
      listener: (this: HTMLElement, ev: HTMXEventMap[K]) => void,
      options?: boolean | AddEventListenerOptions
    ): void;
    addEventListener(
      type: string,
      listener: EventListenerOrEventListenerObject,
      options?: boolean | AddEventListenerOptions
    ): void;
  }
}

export {};