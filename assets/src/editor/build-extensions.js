import { StarterKit } from '@tiptap/starter-kit';
import { TaskList } from '@tiptap/extension-task-list';
import { TaskItem } from '@tiptap/extension-task-item';
import { TextStyle } from '@tiptap/extension-text-style';
import { Color } from '@tiptap/extension-color';
import { FontFamily } from '@tiptap/extension-font-family';
import { Highlight } from '@tiptap/extension-highlight';
import { TableKit } from '@tiptap/extension-table';

import { FontSize } from './extensions/font-size.js';
import { MoveBlock } from './extensions/move-block.js';
import { LocalImage } from './extensions/local-image.js';
import { LocalAudio } from './extensions/local-audio.js';

// options.resolveMedia: async (mediaId, { kind: 'image' | 'audio' }) => { url, revoke? } | null
// 각 mediaId 종류별로 다른 resolver를 쓰고 싶으면 { image: fn, audio: fn } 형태로도 줄 수 있다.
function pickResolver(resolveMedia, kind) {
  if (typeof resolveMedia === 'function') return resolveMedia;
  if (resolveMedia && typeof resolveMedia[kind] === 'function') return resolveMedia[kind];
  return null;
}

export function buildExtensions(options = {}) {
  const resolveMedia = options.resolveMedia || null;

  return [
    StarterKit.configure({
      // Link은 StarterKit 기본 포함. 자동 링크는 켜 두되 클릭 시 새 창 이동은
      // 호스트 UI(index.html)의 몫이라 openOnClick은 끈다 (편집 중 실수 이동 방지).
      link: {
        openOnClick: false,
        autolink: true,
        HTMLAttributes: { rel: 'noopener noreferrer', target: '_blank' },
      },
      // 목록 관련 키맵/자식 타입은 기본값 유지.
      ...(options.starterKit || {}),
    }),
    TaskList,
    TaskItem.configure({ nested: true }),
    TextStyle,
    Color,
    FontFamily,
    FontSize,
    Highlight.configure({ multicolor: true }),
    TableKit.configure({
      table: { resizable: false },
    }),
    MoveBlock,
    LocalImage.configure({
      resolveMedia: pickResolver(resolveMedia, 'image'),
      unresolvedText: options.unresolvedMediaText || null,
    }),
    LocalAudio.configure({
      resolveMedia: pickResolver(resolveMedia, 'audio'),
      unresolvedText: options.unresolvedMediaText || null,
    }),
    ...(options.extraExtensions || []),
  ];
}

export default buildExtensions;
