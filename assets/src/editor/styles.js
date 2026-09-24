// 에디터 콘텐츠에 필요한 최소 구조 CSS. index.html의 색상 체계(다크모드 변수 등)를
// 침범하지 않도록 색상은 최소한만 지정하고 나머지는 상속에 맡긴다.
// 마운트 시 1회만 <style id="buzzplan-editor-style">로 주입된다 (styleId 상수 참조).
export const STYLE_ELEMENT_ID = 'buzzplan-editor-style';

export const EDITOR_CSS = `
.bzp-editor { outline: none; line-height: 1.5; word-break: break-word; }
.bzp-editor > * + * { margin-top: 0.6em; }
.bzp-editor h1, .bzp-editor h2, .bzp-editor h3 { line-height: 1.25; font-weight: 700; }
.bzp-editor h1 { font-size: 1.5em; }
.bzp-editor h2 { font-size: 1.25em; }
.bzp-editor h3 { font-size: 1.1em; }
.bzp-editor ul, .bzp-editor ol { padding-left: 1.4em; }
.bzp-editor code { background: rgba(120,120,120,0.16); border-radius: 3px; padding: 0.1em 0.3em; font-size: 0.92em; }
.bzp-editor pre { background: rgba(120,120,120,0.12); border-radius: 6px; padding: 0.7em 0.9em; overflow-x: auto; }
.bzp-editor pre code { background: none; padding: 0; }
.bzp-editor blockquote { border-left: 3px solid rgba(120,120,120,0.4); margin: 0; padding-left: 0.9em; opacity: 0.9; }
.bzp-editor a { color: #4a90e2; text-decoration: underline; }
.bzp-editor mark { border-radius: 2px; padding: 0 0.05em; }

.bzp-editor ul[data-type="taskList"] { list-style: none; padding-left: 0.2em; }
.bzp-editor ul[data-type="taskList"] li { display: flex; align-items: flex-start; gap: 0.4em; }
.bzp-editor ul[data-type="taskList"] li > label { flex: 0 0 auto; margin-top: 0.2em; }
.bzp-editor ul[data-type="taskList"] li > div { flex: 1 1 auto; }
.bzp-editor ul[data-type="taskList"] li[data-checked="true"] > div { text-decoration: line-through; opacity: 0.6; }

.bzp-editor table { border-collapse: collapse; table-layout: fixed; width: 100%; }
.bzp-editor th, .bzp-editor td { border: 1px solid rgba(120,120,120,0.35); padding: 0.35em 0.5em; vertical-align: top; }
.bzp-editor th { background: rgba(120,120,120,0.12); font-weight: 700; text-align: left; }

.bzp-media { margin: 0; border-radius: 6px; }
.bzp-media-image .bzp-media-img { max-width: 100%; border-radius: 6px; display: block; }
.bzp-media-caption { font-size: 0.85em; opacity: 0.75; margin-top: 0.25em; }
.bzp-media-title { display: block; font-size: 0.85em; opacity: 0.75; margin-bottom: 0.25em; }
.bzp-media-audio-el { width: 100%; }
.bzp-media-placeholder {
  border: 1px dashed rgba(120,120,120,0.5);
  border-radius: 6px;
  padding: 0.6em 0.8em;
  font-size: 0.85em;
  font-style: italic;
  opacity: 0.7;
}
.bzp-media-unresolved { opacity: 0.9; }
`;

export function ensureEditorStylesInjected(doc = document) {
  if (doc.getElementById(STYLE_ELEMENT_ID)) return;
  const style = doc.createElement('style');
  style.id = STYLE_ELEMENT_ID;
  style.textContent = EDITOR_CSS;
  doc.head.appendChild(style);
}
