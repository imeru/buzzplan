// 글자 크기 확장.
//
// Tiptap v3 공식 패키지에는 안정판 font-size 확장이 없다 (@tiptap/extension-font-size는
// 2026-09 기준 3.0.0-next.3 프리릴리스뿐이라 이 프로젝트의 "공식 pinned MIT 패키지" 기준에
// 맞지 않는다). 대신 Tiptap 문서가 권장하는 방식대로 @tiptap/extension-text-style의
// textStyle 마크에 fontSize 속성을 얹는다. textStyle 자체는 안정판이라 이 확장은
// 신뢰할 수 있는 공식 API(addGlobalAttributes/addCommands) 위에서만 동작한다.
import { Extension } from '@tiptap/core';

export const FontSize = Extension.create({
  name: 'fontSize',

  addOptions() {
    return { types: ['textStyle'] };
  },

  addGlobalAttributes() {
    return [
      {
        types: this.options.types,
        attributes: {
          fontSize: {
            default: null,
            parseHTML: (element) => element.style.fontSize || null,
            renderHTML: (attributes) => {
              if (!attributes.fontSize) return {};
              return { style: `font-size: ${attributes.fontSize}` };
            },
          },
        },
      },
    ];
  },

  addCommands() {
    return {
      setFontSize:
        (fontSize) =>
        ({ chain }) =>
          chain().setMark('textStyle', { fontSize }).run(),
      unsetFontSize:
        () =>
        ({ chain }) =>
          chain().setMark('textStyle', { fontSize: null }).removeEmptyTextStyle().run(),
    };
  },
});

export default FontSize;
