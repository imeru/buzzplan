// BuzzPlan 리치 텍스트 메모 에디터 (Tiptap v3 기반).
//
// 이 파일은 assets/vendor/buzzplan-editor.mjs로 번들되어 index.html에서
//   const { createEditor } = await import('./assets/vendor/buzzplan-editor.mjs');
// 형태로 동적 import되는 것을 전제로 한 순수 바닐라 API다. Tiptap/ProseMirror
// 개념(Editor, chain, Node 등)은 이 파일 밖으로 새 나가지 않는다.
//
// index.html이나 기존 동기화 코드는 이 번들이 건드리지 않는다. 실제 툴바 UI,
// notes 필드와의 연결, mediaId ↔ 실제 파일 저장(IndexedDB 등) 연동은 전부
// 호스트 쪽에서 이 API 위에 얹는 몫이다.
import { Editor } from '@tiptap/core';

import { buildExtensions } from './build-extensions.js';
import { createCommandApi } from './commands.js';
import { ensureEditorStylesInjected } from './styles.js';

export const VERSION = '1.0.0';
export const TIPTAP_VERSION = '3.31.3';

// 빈 문서 여부 판단: 텍스트가 없고 atom 노드(이미지/오디오/표 등)도 없을 때만 true.
function computeIsEmpty(editor) {
  if (editor.isEmpty) return true;
  const doc = editor.state.doc;
  if (doc.textContent.trim().length > 0) return false;
  let hasLeaf = false;
  doc.descendants((node) => {
    if (!node.isText && node.isLeaf) hasLeaf = true;
  });
  return !hasLeaf;
}

export class BuzzPlanEditor {
  /**
   * @param {HTMLElement} element - 에디터를 마운트할 빈 컨테이너.
   * @param {object} [options]
   * @param {object|string} [options.content] - 초기 콘텐츠 (Tiptap JSON, HTML 문자열, 또는 빈 값).
   * @param {boolean} [options.editable=true]
   * @param {string} [options.placeholder] - (플레이스홀더 확장은 별도 패키지가 필요해 미포함;
   *   대신 호스트가 CSS로 처리하고 싶다면 이 값을 data-placeholder 속성으로만 남겨 둔다.)
   * @param {Function|{image?:Function, audio?:Function}} [options.resolveMedia] -
   *   mediaId → 실제 표시 URL 해석 함수. 상세 계약은 extensions/media-common.js 참고.
   * @param {string|Function} [options.unresolvedMediaText] - 파일이 없는 첨부에 표시할 번역된 문구.
   * @param {(payload: {editor: BuzzPlanEditor, json: object, text: string, empty: boolean}) => void} [options.onUpdate]
   * @param {(payload: {editor: BuzzPlanEditor}) => void} [options.onSelectionUpdate]
   * @param {(payload: {editor: BuzzPlanEditor}) => void} [options.onReady]
   * @param {(payload: {editor: BuzzPlanEditor}) => void} [options.onDestroy]
   * @param {object} [options.extraExtensions] - 고급 사용을 위한 추가 Tiptap 확장 배열.
   */
  constructor(element, options = {}) {
    if (!element) throw new Error('createEditor(element, options)에는 마운트할 DOM 요소가 필요합니다');

    this._options = options;
    this._destroyed = false;
    this._listeners = new Map(); // event -> Set<fn>  (외부에 노출하는 on/off 전용, tiptap 이벤트와 별개)

    ensureEditorStylesInjected(element.ownerDocument || document);

    if (options.placeholder) element.setAttribute('data-placeholder', options.placeholder);

    this.editor = new Editor({
      element,
      editable: options.editable !== false,
      extensions: buildExtensions(options),
      content: options.content ?? '',
      autofocus: options.autofocus ?? false,
      editorProps: {
        attributes: { class: 'bzp-editor' },
      },
      onCreate: () => {
        options.onReady?.({ editor: this });
        this._emit('ready', { editor: this });
      },
      onUpdate: () => {
        const payload = { editor: this, json: this.getJSON(), text: this.getText(), empty: this.isEmpty() };
        options.onUpdate?.(payload);
        this._emit('update', payload);
      },
      onSelectionUpdate: () => {
        const payload = { editor: this };
        options.onSelectionUpdate?.(payload);
        this._emit('selectionUpdate', payload);
      },
      onDestroy: () => {
        options.onDestroy?.({ editor: this });
        this._emit('destroy', { editor: this });
      },
    });

    this.commands = createCommandApi(this.editor);
  }

  // --- 콘텐츠 ---

  /** Tiptap JSON 문서를 돌려준다 (JSON.stringify 가능한 순수 객체). */
  getJSON() {
    return this.editor.getJSON();
  }

  /** JSON 문서로 콘텐츠를 통째로 교체한다. emitUpdate=false면 update 이벤트를 억제한다. */
  setJSON(json, { emitUpdate = true } = {}) {
    this.editor.commands.setContent(json ?? '', { emitUpdate });
  }

  /** 평문 텍스트를 돌려준다 (문단 경계는 blockSeparator로 이어 붙인다). */
  getText({ blockSeparator = '\n\n' } = {}) {
    return this.editor.getText({ blockSeparator });
  }

  isEmpty() {
    return computeIsEmpty(this.editor);
  }

  // --- 포커스 / 상태 조회 ---

  focus(position) {
    this.editor.chain().focus(position).run();
  }

  /** 툴바 버튼의 활성(on/off) 상태 조회. 예: isActive('bold'), isActive('heading', {level:2}) */
  isActive(name, attrs) {
    return this.editor.isActive(name, attrs);
  }

  /** 특정 명령을 지금 실행할 수 있는지 (툴바 버튼 disabled 판정용). */
  can(name, ...args) {
    const chain = this.editor.can().chain().focus();
    if (typeof chain[name] !== 'function') return false;
    return chain[name](...args).run();
  }

  // --- 이벤트 ---

  /** 'update' | 'selectionUpdate' | 'ready' | 'destroy' */
  on(event, callback) {
    if (!this._listeners.has(event)) this._listeners.set(event, new Set());
    this._listeners.get(event).add(callback);
    return () => this.off(event, callback);
  }

  off(event, callback) {
    this._listeners.get(event)?.delete(callback);
  }

  _emit(event, payload) {
    this._listeners.get(event)?.forEach((fn) => {
      try {
        fn(payload);
      } catch (err) {
        // 호스트 콜백 오류가 에디터 자체를 죽이지 않게 한다.
        console.error('[buzzplan-editor] listener error:', err);
      }
    });
  }

  // --- 수명주기 ---

  destroy() {
    if (this._destroyed) return;
    this._destroyed = true;
    this.editor.destroy();
    this._listeners.clear();
  }
}

/**
 * 컨테이너에 에디터를 마운트한다.
 * @param {HTMLElement} element
 * @param {object} [options] - BuzzPlanEditor 생성자 옵션 참고.
 * @returns {BuzzPlanEditor}
 */
export function createEditor(element, options = {}) {
  return new BuzzPlanEditor(element, options);
}

export default createEditor;
