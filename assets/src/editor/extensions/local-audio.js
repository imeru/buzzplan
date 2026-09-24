// mediaId로 참조하는 로컬 오디오 노드. local-image.js와 같은 mediaId 계약을 쓴다.
import { Node, mergeAttributes } from '@tiptap/core';
import { resolveMediaInto, placeholderText } from './media-common.js';

export const LocalAudio = Node.create({
  name: 'localAudio',
  group: 'block',
  atom: true,
  draggable: true,
  selectable: true,

  addOptions() {
    return {
      HTMLAttributes: {},
      // async (mediaId, { kind }) => { url, revoke? } | null
      resolveMedia: null,
      unresolvedText: null,
    };
  },

  addAttributes() {
    return {
      mediaId: { default: null },
      title: { default: '' },
      durationSec: { default: null },
    };
  },

  parseHTML() {
    return [{ tag: 'div[data-media-kind="audio"]' }];
  },

  renderHTML({ node, HTMLAttributes }) {
    const attrs = mergeAttributes(this.options.HTMLAttributes, HTMLAttributes, {
      'data-media-kind': 'audio',
      'data-media-id': node.attrs.mediaId || '',
    });
    const audio = ['audio', { controls: 'controls', 'data-media-id': node.attrs.mediaId || '' }];
    if (node.attrs.title) {
      return ['div', attrs, ['span', { class: 'bzp-media-title' }, node.attrs.title], audio];
    }
    return ['div', attrs, audio];
  },

  addNodeView() {
    return ({ node, getPos }) => {
      const resolveMedia = this.options.resolveMedia;

      const dom = document.createElement('div');
      dom.setAttribute('data-media-kind', 'audio');
      dom.setAttribute('data-media-id', node.attrs.mediaId || '');
      dom.className = 'bzp-media bzp-media-audio';

      const titleEl = document.createElement('span');
      titleEl.className = 'bzp-media-title';
      titleEl.textContent = node.attrs.title || '';
      titleEl.hidden = !node.attrs.title;
      dom.appendChild(titleEl);

      const audio = document.createElement('audio');
      audio.controls = true;
      audio.className = 'bzp-media-audio-el';
      dom.appendChild(audio);

      const setUnresolved = (message) => {
        dom.classList.add('bzp-media-unresolved');
        audio.replaceWith(Object.assign(document.createElement('div'), {
          className: 'bzp-media-placeholder',
          textContent: message,
        }));
      };

      let resolution = { cancel() {} };
      if (typeof getPos === 'function') {
        resolution = resolveMediaInto({
          resolveMedia,
          mediaId: node.attrs.mediaId,
          kind: 'audio',
          onResolved: (url) => {
            audio.src = url;
          },
          onError: () => setUnresolved(placeholderText(node.attrs.mediaId, 'audio', this.options.unresolvedText)),
        });
      }
      if (!resolveMedia) setUnresolved(placeholderText(node.attrs.mediaId, 'audio', this.options.unresolvedText));

      return {
        dom,
        ignoreMutation: () => true,
        update: (updatedNode) => {
          if (updatedNode.type.name !== 'localAudio') return false;
          // mediaId 변경은 기존 URL을 해제하고 resolver를 다시 실행해야 하므로 재생성한다.
          if (updatedNode.attrs.mediaId !== node.attrs.mediaId) return false;
          node = updatedNode;
          dom.setAttribute('data-media-id', node.attrs.mediaId || '');
          titleEl.textContent = node.attrs.title || '';
          titleEl.hidden = !node.attrs.title;
          return true;
        },
        destroy: () => {
          resolution.cancel();
        },
      };
    };
  },

  addCommands() {
    return {
      insertLocalAudio:
        (attrs) =>
        ({ chain }) =>
          chain()
            .insertContent([
              { type: this.name, attrs: { title: '', durationSec: null, ...attrs } },
              { type: 'paragraph' },
            ])
            .run(),
    };
  },
});

export default LocalAudio;
