// mediaId로 참조하는 로컬 이미지 노드.
//
// doc JSON에는 { type: 'localImage', attrs: { mediaId, alt, caption } } 만 남는다.
// 실제 표시용 URL은 마운트 시점에 options.resolveMedia(mediaId, { kind: 'image' })를
// 통해 비동기로 구한다 (예: IndexedDB에 저장된 Blob → URL.createObjectURL).
// 이 파일은 그 resolver가 없어도 깨지지 않고, 자리표시자를 그려 통합 지점을 드러낸다.
import { Node, mergeAttributes } from '@tiptap/core';
import { resolveMediaInto, placeholderText } from './media-common.js';

export const LocalImage = Node.create({
  name: 'localImage',
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
      alt: { default: '' },
      caption: { default: '' },
      width: { default: null }, // 예: "320px" 또는 "60%"
    };
  },

  parseHTML() {
    return [{ tag: 'figure[data-media-kind="image"]' }];
  },

  renderHTML({ node, HTMLAttributes }) {
    // 서버 없는 정적 배포라 img src는 항상 미해결 상태로 직렬화된다.
    // 실제 URL 주입은 NodeView가 마운트 후에 담당한다.
    const attrs = mergeAttributes(this.options.HTMLAttributes, HTMLAttributes, {
      'data-media-kind': 'image',
      'data-media-id': node.attrs.mediaId || '',
    });
    const img = ['img', { alt: node.attrs.alt || '', 'data-media-id': node.attrs.mediaId || '' }];
    if (node.attrs.caption) {
      return ['figure', attrs, img, ['figcaption', {}, node.attrs.caption]];
    }
    return ['figure', attrs, img];
  },

  addNodeView() {
    return ({ node, editor, getPos }) => {
      const resolveMedia = this.options.resolveMedia;

      const dom = document.createElement('figure');
      dom.setAttribute('data-media-kind', 'image');
      dom.setAttribute('data-media-id', node.attrs.mediaId || '');
      dom.className = 'bzp-media bzp-media-image';
      if (node.attrs.width) dom.style.width = node.attrs.width;

      const img = document.createElement('img');
      img.alt = node.attrs.alt || '';
      img.className = 'bzp-media-img';
      dom.appendChild(img);

      const figcaption = document.createElement('figcaption');
      figcaption.className = 'bzp-media-caption';
      figcaption.textContent = node.attrs.caption || '';
      figcaption.hidden = !node.attrs.caption;
      dom.appendChild(figcaption);

      const setUnresolved = (message) => {
        dom.classList.add('bzp-media-unresolved');
        img.replaceWith(Object.assign(document.createElement('div'), {
          className: 'bzp-media-placeholder',
          textContent: message,
        }));
      };

      let resolution = { cancel() {} };
      if (typeof getPos === 'function') {
        resolution = resolveMediaInto({
          resolveMedia,
          mediaId: node.attrs.mediaId,
          kind: 'image',
          onResolved: (url) => {
            img.src = url;
          },
          onError: () => setUnresolved(placeholderText(node.attrs.mediaId, 'image', this.options.unresolvedText)),
        });
      }
      if (!resolveMedia) setUnresolved(placeholderText(node.attrs.mediaId, 'image', this.options.unresolvedText));

      return {
        dom,
        ignoreMutation: () => true,
        update: (updatedNode) => {
          if (updatedNode.type.name !== 'localImage') return false;
          // mediaId가 바뀌면 기존 object URL을 해제하고 resolver를 다시 실행해야 한다.
          // false를 반환하면 ProseMirror가 이 NodeView를 destroy한 뒤 새로 만든다.
          if (updatedNode.attrs.mediaId !== node.attrs.mediaId) return false;
          node = updatedNode;
          dom.setAttribute('data-media-id', node.attrs.mediaId || '');
          figcaption.textContent = node.attrs.caption || '';
          figcaption.hidden = !node.attrs.caption;
          img.alt = node.attrs.alt || '';
          dom.style.width = node.attrs.width || '';
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
      insertLocalImage:
        (attrs) =>
        ({ chain }) =>
          chain()
            .insertContent([
              { type: this.name, attrs: { alt: '', caption: '', width: null, ...attrs } },
              { type: 'paragraph' },
            ])
            .run(),
    };
  },
});

export default LocalImage;
