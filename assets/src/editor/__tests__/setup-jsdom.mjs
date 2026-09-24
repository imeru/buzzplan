// 헤드리스 DOM 환경 부트스트랩. Tiptap/ProseMirror는 실제 브라우저 DOM API를
// 상당수 요구하므로(Range, Selection, MutationObserver, matchMedia 등) jsdom만으로는
// 부족한 몇 가지를 최소한으로 메운다. 실제 브라우저 검증은 대체하지 못하며,
// 이 테스트는 "API 계약이 깨지지 않았는가"를 보는 회귀 스모크 테스트다.
import { JSDOM } from 'jsdom';

export function installJsdomGlobals() {
  const dom = new JSDOM('<!doctype html><html><body></body></html>', {
    url: 'http://localhost/',
    pretendToBeVisual: true,
  });
  const { window } = dom;

  // Node.js 21+는 전역 `navigator`를 getter로 이미 정의해 두므로 일반 대입이 아니라
  // defineProperty로 덮어써야 한다.
  const defineGlobal = (name, value) => {
    Object.defineProperty(global, name, { value, configurable: true, writable: true });
  };

  defineGlobal('window', window);
  defineGlobal('document', window.document);
  defineGlobal('navigator', window.navigator);
  defineGlobal('Node', window.Node);
  global.Element = window.Element;
  global.HTMLElement = window.HTMLElement;
  global.DocumentFragment = window.DocumentFragment;
  global.getComputedStyle = window.getComputedStyle;
  global.requestAnimationFrame = (cb) => setTimeout(() => cb(Date.now()), 0);
  global.cancelAnimationFrame = (id) => clearTimeout(id);

  if (!window.matchMedia) {
    window.matchMedia = () => ({
      matches: false,
      addListener() {},
      removeListener() {},
      addEventListener() {},
      removeEventListener() {},
    });
  }
  global.matchMedia = window.matchMedia;

  if (!window.ResizeObserver) {
    window.ResizeObserver = class ResizeObserver {
      observe() {}
      unobserve() {}
      disconnect() {}
    };
  }
  global.ResizeObserver = window.ResizeObserver;

  // jsdom은 레이아웃 엔진이 없어 Range.getClientRects/getBoundingClientRect가
  // 아예 구현되어 있지 않다. ProseMirror-view는 커서를 옮길 때마다
  // (scrollIntoView, coordsAtPos 등) 이 API로 화면 좌표를 구하려 하므로,
  // 폴백 없이는 "n.getClientRects is not a function"으로 죽는다.
  // 실제 좌표는 의미가 없으니(레이아웃이 없다) 빈 값을 돌려주는 자리만 채운다.
  const zeroRect = () => ({
    x: 0, y: 0, top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0, toJSON() { return this; },
  });
  window.Range.prototype.getClientRects = function getClientRects() { return []; };
  window.Range.prototype.getBoundingClientRect = function getBoundingClientRect() { return zeroRect(); };
  if (window.Element && !window.Element.prototype.getClientRects) {
    window.Element.prototype.getClientRects = function getClientRects() { return []; };
  }
  if (window.Element && !window.Element.prototype.getBoundingClientRect) {
    window.Element.prototype.getBoundingClientRect = function getBoundingClientRect() { return zeroRect(); };
  }

  return dom;
}
