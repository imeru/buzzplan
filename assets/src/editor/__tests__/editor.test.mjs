// 회귀 스모크 테스트: assets/vendor/buzzplan-editor.mjs (실제 배포되는 생성 번들)를
// jsdom 위에서 마운트해 공개 API 계약이 깨지지 않았는지 확인한다.
// npm run build를 먼저 실행해 번들을 생성해 둬야 한다 (npm test / npm run check가 자동 처리).
import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { installJsdomGlobals } from './setup-jsdom.mjs';

installJsdomGlobals();

const here = path.dirname(fileURLToPath(import.meta.url));
const bundlePath = path.resolve(here, '../../../vendor/buzzplan-editor.mjs');
const { createEditor } = await import(pathToFileURL(bundlePath).href);

function makeContainer() {
  const el = document.createElement('div');
  document.body.appendChild(el);
  return el;
}

test('마운트 후 초기 텍스트를 읽을 수 있다', () => {
  const el = makeContainer();
  const editor = createEditor(el, {
    content: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Hello BuzzPlan' }] }] },
  });
  assert.equal(editor.getText().trim(), 'Hello BuzzPlan');
  assert.equal(editor.isEmpty(), false);
  editor.destroy();
});

test('빈 에디터는 isEmpty() true다', () => {
  const el = makeContainer();
  const editor = createEditor(el, {});
  assert.equal(editor.isEmpty(), true);
  editor.destroy();
});

test('getJSON/setJSON 라운드트립이 보존된다', () => {
  const el = makeContainer();
  const editor = createEditor(el, {});
  const doc = {
    type: 'doc',
    content: [
      { type: 'heading', attrs: { level: 2 }, content: [{ type: 'text', text: '제목' }] },
      { type: 'paragraph', content: [{ type: 'text', text: '본문', marks: [{ type: 'bold' }] }] },
    ],
  };
  editor.setJSON(doc);
  const roundtrip = editor.getJSON();
  assert.equal(roundtrip.content[0].type, 'heading');
  assert.equal(roundtrip.content[0].attrs.level, 2);
  assert.equal(roundtrip.content[1].content[0].marks[0].type, 'bold');
  editor.destroy();
});

test('toggleBold/toggleHeading 커맨드가 isActive에 반영된다', () => {
  const el = makeContainer();
  const editor = createEditor(el, {
    content: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'abc' }] }] },
  });
  editor.editor.commands.selectAll();
  assert.equal(editor.commands.toggleBold(), true);
  assert.equal(editor.isActive('bold'), true);

  // 커서를 문단 안 한 지점으로 되돌린 뒤 토글한다. StarterKit의 TrailingNode
  // 확장이 헤딩 뒤에 빈 문단을 자동으로 붙이므로, selectAll을 그대로 두면
  // 전체선택(AllSelection)이 그 새 문단까지 덮어 isActive가 항상 false로 나온다.
  editor.editor.commands.setTextSelection(1);
  assert.equal(editor.commands.toggleHeading(3), true);
  assert.equal(editor.isActive('heading', { level: 3 }), true);
  editor.destroy();
});

test('toggleBulletList / toggleOrderedList / toggleTaskList', () => {
  const el = makeContainer();
  const editor = createEditor(el, {
    content: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'item' }] }] },
  });
  assert.equal(editor.commands.toggleBulletList(), true);
  assert.equal(editor.isActive('bulletList'), true);
  assert.equal(editor.commands.toggleBulletList(), true); // 다시 눌러 해제
  assert.equal(editor.isActive('bulletList'), false);

  assert.equal(editor.commands.toggleOrderedList(), true);
  assert.equal(editor.isActive('orderedList'), true);
  editor.commands.toggleOrderedList();

  assert.equal(editor.commands.toggleTaskList(), true);
  assert.equal(editor.isActive('taskList'), true);
  editor.destroy();
});

test('font family / font size / color / highlight 커맨드', () => {
  const el = makeContainer();
  const editor = createEditor(el, {
    content: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'colorme' }] }] },
  });
  editor.editor.commands.selectAll();
  assert.equal(editor.commands.setFontFamily('Georgia'), true);
  assert.equal(editor.isActive('textStyle', { fontFamily: 'Georgia' }), true);

  assert.equal(editor.commands.setFontSize('18px'), true);
  assert.equal(editor.isActive('textStyle', { fontSize: '18px' }), true);

  assert.equal(editor.commands.setColor('#ff0000'), true);
  assert.equal(editor.isActive('textStyle', { color: '#ff0000' }), true);

  assert.equal(editor.commands.toggleHighlight('#ffff00'), true);
  assert.equal(editor.isActive('highlight', { color: '#ffff00' }), true);
  editor.destroy();
});

test('setLink / unsetLink', () => {
  const el = makeContainer();
  const editor = createEditor(el, {
    content: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'linktext' }] }] },
  });
  editor.editor.commands.selectAll();
  assert.equal(editor.commands.setLink('https://example.com'), true);
  assert.equal(editor.isActive('link'), true);
  assert.equal(editor.commands.unsetLink(), true);
  assert.equal(editor.isActive('link'), false);
  editor.destroy();
});

test('insertTable로 표를 삽입할 수 있다', () => {
  const el = makeContainer();
  const editor = createEditor(el, {});
  assert.equal(editor.commands.insertTable(2, 2, true), true);
  const json = editor.getJSON();
  assert.equal(json.content[0].type, 'table');
  editor.destroy();
});

test('toggleCodeBlock', () => {
  const el = makeContainer();
  const editor = createEditor(el, {
    content: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'code' }] }] },
  });
  assert.equal(editor.commands.toggleCodeBlock(), true);
  assert.equal(editor.isActive('codeBlock'), true);
  editor.destroy();
});

test('undo/redo가 되돌리기를 수행한다', () => {
  const el = makeContainer();
  const editor = createEditor(el, {
    content: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'v1' }] }] },
  });
  // content.size(4)는 문단이 닫히는 문서 경계 위치라 그대로 삽입하면 ProseMirror가
  // 새 문단으로 감싼다. 문단 안(경계 바로 앞인 content.size - 1)에 넣어야
  // 기존 문단 텍스트 뒤에 이어붙는다.
  editor.editor.commands.insertContentAt(editor.editor.state.doc.content.size - 1, '!!!');
  assert.match(editor.getText(), /v1!!!/);
  editor.commands.undo();
  assert.equal(editor.getText().trim(), 'v1');
  editor.commands.redo();
  assert.match(editor.getText(), /v1!!!/);
  editor.destroy();
});

test('moveBlockUp / moveBlockDown이 최상위 블록 순서를 바꾼다', () => {
  const el = makeContainer();
  const editor = createEditor(el, {
    content: {
      type: 'doc',
      content: [
        { type: 'paragraph', content: [{ type: 'text', text: 'First' }] },
        { type: 'paragraph', content: [{ type: 'text', text: 'Second' }] },
        { type: 'paragraph', content: [{ type: 'text', text: 'Third' }] },
      ],
    },
  });
  // 커서를 두 번째 문단("Second")에 놓는다.
  const secondBlockPos = editor.editor.state.doc.content.child(0).nodeSize + 1;
  editor.editor.commands.setTextSelection(secondBlockPos);

  assert.equal(editor.commands.moveBlockUp(), true);
  let texts = editor.getJSON().content.map((n) => n.content?.[0]?.text);
  assert.deepEqual(texts, ['Second', 'First', 'Third']);

  assert.equal(editor.commands.moveBlockDown(), true);
  texts = editor.getJSON().content.map((n) => n.content?.[0]?.text);
  assert.deepEqual(texts, ['First', 'Second', 'Third']);

  // 맨 위 블록은 더 위로 이동할 수 없다.
  editor.editor.commands.setTextSelection(1);
  assert.equal(editor.commands.moveBlockUp(), false);
  editor.destroy();
});

test('insertLocalImage / insertLocalAudio는 mediaId를 doc JSON에 보존한다', () => {
  const el = makeContainer();
  const editor = createEditor(el, {}); // resolveMedia 없음: 미해결 자리표시자로 렌더되어야 함
  assert.equal(editor.commands.insertLocalImage('img-1', { alt: '설명' }), true);
  let json = editor.getJSON();
  const imageNode = json.content.find((n) => n.type === 'localImage');
  assert.equal(imageNode.attrs.mediaId, 'img-1');
  assert.equal(imageNode.attrs.alt, '설명');
  assert.ok(el.querySelector('.bzp-media-placeholder'), 'resolveMedia 없이는 자리표시자가 보여야 한다');

  assert.equal(editor.commands.insertLocalAudio('aud-1'), true);
  json = editor.getJSON();
  const audioNode = json.content.find((n) => n.type === 'localAudio');
  assert.equal(audioNode.attrs.mediaId, 'aud-1');
  editor.destroy();
});

test('로컬 미디어를 연속 삽입해도 앞 노드를 덮어쓰지 않는다', () => {
  const el = makeContainer();
  const editor = createEditor(el, {});
  assert.equal(editor.commands.insertLocalImage('img-1'), true);
  assert.equal(editor.commands.insertLocalImage('img-2'), true);
  assert.equal(editor.commands.insertLocalAudio('aud-1'), true);

  const media = editor.getJSON().content
    .filter((n) => n.type === 'localImage' || n.type === 'localAudio')
    .map((n) => [n.type, n.attrs.mediaId]);
  assert.deepEqual(media, [
    ['localImage', 'img-1'],
    ['localImage', 'img-2'],
    ['localAudio', 'aud-1'],
  ]);
  editor.destroy();
});

test('미해결 미디어 자리표시자는 호스트 번역 문구를 사용한다', async () => {
  const el = makeContainer();
  const editor = createEditor(el, {
    content: {
      type: 'doc',
      content: [
        { type: 'localImage', attrs: { mediaId: 'img-missing' } },
        { type: 'localAudio', attrs: { mediaId: 'aud-missing' } },
      ],
    },
    resolveMedia: async () => null,
    unresolvedMediaText: (_mediaId, { kind }) => `Missing ${kind} on this device`,
  });
  await new Promise((resolve) => setTimeout(resolve, 10));
  const placeholders = [...el.querySelectorAll('.bzp-media-placeholder')].map((n) => n.textContent);
  assert.deepEqual(placeholders, [
    'Missing image on this device',
    'Missing audio on this device',
  ]);
  assert.deepEqual(
    editor.getJSON().content.map((n) => n.attrs.mediaId),
    ['img-missing', 'aud-missing'],
  );
  editor.destroy();
});

test('resolveMedia가 주어지면 mediaId를 실제 URL로 해석한다', async () => {
  const el = makeContainer();
  const seen = [];
  const editor = createEditor(el, {
    resolveMedia: async (mediaId, { kind }) => {
      seen.push([mediaId, kind]);
      return { url: `blob://${mediaId}` };
    },
  });
  editor.commands.insertLocalImage('img-42');
  // NodeView의 비동기 resolveMedia가 처리될 때까지 매크로태스크 한 틱 대기.
  await new Promise((resolve) => setTimeout(resolve, 10));
  const img = el.querySelector('img.bzp-media-img');
  assert.ok(img, 'resolveMedia가 있으면 실제 <img>가 그려져야 한다');
  assert.equal(img.src, 'blob://img-42');
  assert.deepEqual(seen[0], ['img-42', 'image']);
  editor.destroy();
});

test('setJSON으로 이미지 mediaId를 바꾸면 기존 URL을 해제하고 다시 해석한다', async () => {
  const el = makeContainer();
  const seen = [];
  const revoked = [];
  const editor = createEditor(el, {
    content: { type: 'doc', content: [{ type: 'localImage', attrs: { mediaId: 'img-a' } }] },
    resolveMedia: async (mediaId, { kind }) => {
      seen.push([mediaId, kind]);
      return { url: `blob://${mediaId}`, revoke: () => revoked.push(mediaId) };
    },
  });
  await new Promise((resolve) => setTimeout(resolve, 10));
  editor.setJSON({ type: 'doc', content: [{ type: 'localImage', attrs: { mediaId: 'img-b' } }] });
  await new Promise((resolve) => setTimeout(resolve, 10));
  assert.deepEqual(seen, [['img-a', 'image'], ['img-b', 'image']]);
  assert.deepEqual(revoked, ['img-a']);
  assert.equal(el.querySelector('img.bzp-media-img').src, 'blob://img-b');
  editor.destroy();
  assert.deepEqual(revoked, ['img-a', 'img-b']);
});

test('setJSON으로 오디오 mediaId를 바꾸면 기존 URL을 해제하고 다시 해석한다', async () => {
  const el = makeContainer();
  const seen = [];
  const revoked = [];
  const editor = createEditor(el, {
    content: { type: 'doc', content: [{ type: 'localAudio', attrs: { mediaId: 'aud-a' } }] },
    resolveMedia: async (mediaId, { kind }) => {
      seen.push([mediaId, kind]);
      return { url: `blob://${mediaId}`, revoke: () => revoked.push(mediaId) };
    },
  });
  await new Promise((resolve) => setTimeout(resolve, 10));
  editor.setJSON({ type: 'doc', content: [{ type: 'localAudio', attrs: { mediaId: 'aud-b' } }] });
  await new Promise((resolve) => setTimeout(resolve, 10));
  assert.deepEqual(seen, [['aud-a', 'audio'], ['aud-b', 'audio']]);
  assert.deepEqual(revoked, ['aud-a']);
  assert.equal(el.querySelector('audio.bzp-media-audio-el').src, 'blob://aud-b');
  editor.destroy();
  assert.deepEqual(revoked, ['aud-a', 'aud-b']);
});

test('update 이벤트가 setJSON에 반응해 발화한다', () => {
  const el = makeContainer();
  const editor = createEditor(el, {});
  let updateCount = 0;
  let lastText = '';
  editor.on('update', ({ text }) => {
    updateCount += 1;
    lastText = text;
  });
  editor.setJSON({ type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Synced' }] }] });
  assert.equal(updateCount, 1);
  assert.equal(lastText.trim(), 'Synced');
  editor.destroy();
});

test('destroy()는 안전하게 두 번 호출할 수 있고 리스너를 정리한다', () => {
  const el = makeContainer();
  const editor = createEditor(el, {});
  editor.on('update', () => {
    throw new Error('destroy 후에는 절대 호출되면 안 됨');
  });
  editor.destroy();
  assert.doesNotThrow(() => editor.destroy());
});
