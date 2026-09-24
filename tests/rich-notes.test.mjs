import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const indexHtml = fs.readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const rules = fs.readFileSync(new URL('../firestore.rules', import.meta.url), 'utf8');

function extractFunction(name) {
  const startRe = new RegExp(`(?:^|\\n)((?:async\\s+)?function\\s+${name}\\s*\\()`, 'm');
  const hit = startRe.exec(indexHtml);
  assert.ok(hit, `${name} must exist in index.html`);
  const start = hit.index + (indexHtml[hit.index] === '\n' ? 1 : 0);
  const rest = indexHtml.slice(start);
  const next = /\n(?:async\s+)?function\s+[A-Za-z_$][\w$]*\s*\(/.exec(rest.slice(hit[1].length));
  const end = next ? hit[1].length + next.index : rest.length;
  return rest.slice(0, end).trim();
}

function buildModule({ functions, prelude, exports }) {
  const source = functions.map(extractFunction).join('\n\n');
  return new Function(`${prelude}\n${source}\nreturn (${exports});`)();
}

function tick() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

test('richNotes 업로드는 서버 컬렉션 확인 전 시작하지 않는다', async () => {
  const api = buildModule({
    functions: ['rnPushNext'],
    prelude: `
      let rnActive = true;
      let _rnServerSeen = false;
      let _rnPushing = false;
      let _rnUser = { uid: 'u1' };
      let _rnGen = 1;
      let _rnPushTimer = 123;
      let _nbOwner = 'u1';
      let _nbLoaded = true;
      let _nbNotes = new Map([{ id: 'n1', dirty: true }].map(n => [n.id, n]));
      let calls = 0;
      const firebase = {};
      const rnValidate = () => '';
      const rnPushOne = async () => { calls++; return { ok: true, writeId: 'w2' }; };
      const rnAfterPushOk = async () => {};
      const rnResolveConflict = async () => {};
      const rnReportError = () => {};
      const rnIsPermErr = () => false;
      const rnSchedulePush = () => {};
      const nbAfterNotesChanged = () => {};
      const nbRebuildIndex = () => {};
    `,
    exports: `{ run: rnPushNext, calls: () => calls, timer: () => _rnPushTimer }`,
  });

  await api.run();
  assert.equal(api.calls(), 0);
  assert.equal(api.timer(), null);
});

test('richNotes 트랜잭션은 parentWriteId 체인이 맞을 때만 쓴다', async () => {
  const api = buildModule({
    functions: ['rnPushOne'],
    prelude: `
      let snap = null;
      let sets = [];
      const nbNewId = () => 'new-write';
      const rnPayload = (rec, writeId, parentWriteId, createdAt) => ({
        id: rec.id, writeId, parentWriteId, createdAt,
      });
      const rnCol = () => ({ doc: (id) => ({ id }) });
      const firebase = {
        firestore: () => ({
          runTransaction: async (fn) => fn({
            get: async () => snap,
            set: (ref, payload) => sets.push({ ref, payload }),
          }),
        }),
      };
    `,
    exports: `{
      run: async (nextSnap, rec) => {
        snap = nextSnap;
        sets = [];
        const result = await rnPushOne('u1', rec);
        return { result, sets };
      },
    }`,
  });

  let out = await api.run({ exists: false }, { id: 'n1', parentWriteId: null });
  assert.deepEqual(out.result, { ok: true, writeId: 'new-write' });
  assert.equal(out.sets.length, 1);
  assert.equal(out.sets[0].payload.parentWriteId, null);

  out = await api.run({ exists: false }, { id: 'n1', parentWriteId: 'old' });
  assert.deepEqual(out.result, { conflict: true, server: null });
  assert.equal(out.sets.length, 0);

  out = await api.run({
    exists: true,
    data: () => ({ writeId: 'base', createdAt: 'created' }),
  }, { id: 'n1', parentWriteId: 'base' });
  assert.deepEqual(out.result, { ok: true, writeId: 'new-write' });
  assert.equal(out.sets.length, 1);
  assert.equal(out.sets[0].payload.parentWriteId, 'base');
  assert.equal(out.sets[0].payload.createdAt, 'created');

  out = await api.run({
    exists: true,
    data: () => ({ writeId: 'server-newer', createdAt: 'created' }),
  }, { id: 'n1', parentWriteId: 'base' });
  assert.equal(out.result.conflict, true);
  assert.equal(out.result.server.writeId, 'server-newer');
  assert.equal(out.sets.length, 0);
});

test('owner 전환이 겹쳐도 마지막 uid 파티션만 반영한다', async () => {
  const api = buildModule({
    functions: ['nbLoadPartition', 'nbSwitchOwner'],
    prelude: `
      let _nbOwner = 'old-owner';
      let _nbLoaded = true;
      let _nbLoadGen = 0;
      let _nbOwnerSwitchSeq = 0;
      let _nbOwnerSwitchQueue = Promise.resolve();
      let _nbNotes = new Map();
      let currentConfId = 'conf-a';
      const _rnInvalid = new Map();
      const waiters = new Map();
      const NoteStore = {
        list(owner) {
          return new Promise((resolve) => waiters.set(owner, resolve));
        },
      };
      const nbCloseEditor = async () => true;
      const nbRenderPaneState = () => {};
      const nbReportStorageError = (e) => { throw e; };
      const nbNormalize = (row, owner, confId) => ({ ...row, owner, confId, dirty: !!row.dirty });
      const rnCheckValid = () => true;
      const nbRebuildIndex = () => {};
      const nbAfterNotesChanged = () => {};
      const nbRecoverRecordingDrafts = async () => 0;
      const nbScheduleMediaCleanup = () => {};
    `,
    exports: `{
      switchOwner: nbSwitchOwner,
      resolve(owner, rows) { waiters.get(owner)(rows); },
      hasWaiter(owner) { return waiters.has(owner); },
      owner: () => _nbOwner,
      ids: () => [..._nbNotes.keys()],
    }`,
  });

  const guest = api.switchOwner('guest');
  await tick();
  assert.equal(api.hasWaiter('guest'), true);

  const uid = api.switchOwner('uid-1');
  api.resolve('guest', [{ id: 'guest-note' }]);
  await tick();
  await tick();
  assert.equal(api.hasWaiter('uid-1'), true);

  api.resolve('uid-1', [{ id: 'account-note' }]);
  await Promise.all([guest, uid]);

  assert.equal(api.owner(), 'uid-1');
  assert.deepEqual(api.ids(), ['account-note']);
});

test('게스트 재복사는 다른 계정 노트를 덮지 않고 충돌 사본을 만든다', async () => {
  const api = buildModule({
    functions: ['rnSameContent', 'rnMakeConflictCopy', 'rnCopyGuestNotes'],
    prelude: `
      const NB_LIMITS = { title: 200 };
      let currentConfId = 'conf-a';
      let _rnUser = { uid: 'uid-1' };
      let _rnGen = 7;
      let _nbOwner = 'uid-1';
      const _nb = { openId: null };
      const account = {
        id: 'same-id', title: 'account text', body: 'A', deleted: false,
        paperRefs: [], mediaIds: [], updatedAt: 10,
      };
      const _nbNotes = new Map([[account.id, account]]);
      const persisted = [];
      let savedMeta = null;
      const NoteStore = { list: async () => [{
        id: 'same-id', title: 'guest text', body: 'G', deleted: false,
        paperRefs: [], mediaIds: [], updatedAt: 20,
      }] };
      const MetaStore = {
        get: async () => null,
        put: async (_key, value) => { savedMeta = value; },
      };
      const MediaBackend = {
        get: async () => null,
        copy: async () => true,
      };
      const nbStorageEstimate = async () => true;
      const nbNewId = () => 'conflict-copy-id';
      const t = (key) => ({
        nb_conflict_suffix: ' (conflict copy)',
        nb_untitled: 'Untitled',
        nb_guest_copied: 'copied {n}',
      }[key] || key);
      const nbCleanRefs = (v) => Array.isArray(v) ? v : [];
      const nbNormalize = (raw, owner, confId) => ({
        ...raw,
        owner,
        confId,
        title: String(raw.title || ''),
        body: String(raw.body || ''),
        paperRefs: Array.isArray(raw.paperRefs) ? raw.paperRefs : [],
        mediaIds: Array.isArray(raw.mediaIds) ? raw.mediaIds : [],
        deleted: !!raw.deleted,
        updatedAt: Number(raw.updatedAt) || 0,
      });
      const nbPersist = async (rec) => {
        persisted.push(rec);
        _nbNotes.set(rec.id, rec);
        return true;
      };
      const rnCheckValid = () => true;
      const nbReportStorageError = (e) => { throw e; };
      const nbRebuildIndex = () => {};
      const nbAfterNotesChanged = () => {};
      const showToast = () => {};
    `,
    exports: `{
      run: () => rnCopyGuestNotes(7),
      original: () => _nbNotes.get('same-id'),
      copy: () => _nbNotes.get('conflict-copy-id'),
      persisted: () => persisted,
      meta: () => savedMeta,
    }`,
  });

  await api.run();

  assert.equal(api.original().title, 'account text');
  assert.equal(api.copy().title, 'guest text (conflict copy)');
  assert.equal(api.copy().dirty, true);
  assert.equal(api.copy().parentWriteId, null);
  assert.equal(api.persisted().length, 1);
  assert.equal(api.meta().copied['same-id'], 20);
});

test('게스트 첨부 복사 실패는 성공으로 기록하지 않고 다음 로그인을 기다린다', async () => {
  const api = buildModule({
    functions: ['rnSameContent', 'rnMakeConflictCopy', 'rnCopyGuestNotes'],
    prelude: `
      const NB_LIMITS = { title: 200 };
      let currentConfId = 'conf-a';
      let _rnUser = { uid: 'uid-1' };
      let _rnGen = 7;
      let _nbOwner = 'uid-1';
      const _nb = { openId: null };
      const _nbNotes = new Map();
      let savedMeta = null;
      let persisted = 0;
      let reported = null;
      const NoteStore = { list: async () => [{
        id: 'guest-note', title: 'guest', body: 'G', deleted: false,
        paperRefs: [], mediaIds: ['media-1'], updatedAt: 20,
      }] };
      const MetaStore = {
        get: async () => null,
        put: async (_key, value) => { savedMeta = value; },
      };
      const MediaBackend = {
        get: async (owner) => owner === 'guest' ? { id: 'media-1', size: 10 } : null,
        copy: async () => { throw new Error('quota'); },
      };
      const nbStorageEstimate = async () => true;
      const nbNewId = () => 'copy-id';
      const t = (key) => ({
        nb_conflict_suffix: ' (conflict copy)',
        nb_untitled: 'Untitled',
        nb_guest_copied: 'copied {n}',
      }[key] || key);
      const nbCleanRefs = (v) => Array.isArray(v) ? v : [];
      const nbNormalize = (raw, owner, confId) => ({
        ...raw, owner, confId, title: String(raw.title || ''), body: String(raw.body || ''),
        paperRefs: Array.isArray(raw.paperRefs) ? raw.paperRefs : [],
        mediaIds: Array.isArray(raw.mediaIds) ? raw.mediaIds : [],
        deleted: !!raw.deleted, updatedAt: Number(raw.updatedAt) || 0,
      });
      const nbPersist = async () => { persisted++; return true; };
      const rnCheckValid = () => true;
      const nbReportStorageError = (e) => { reported = e.message; };
      const nbRebuildIndex = () => {};
      const nbAfterNotesChanged = () => {};
      const showToast = () => {};
    `,
    exports: `{
      run: () => rnCopyGuestNotes(7),
      persisted: () => persisted,
      meta: () => savedMeta,
      reported: () => reported,
    }`,
  });

  await api.run();
  assert.equal(api.persisted(), 0);
  assert.equal(api.meta(), null);
  assert.equal(api.reported(), 'quota');
});

test('충돌 처리 중 추가 입력은 원본이 아니라 충돌 사본으로 저장한다', async () => {
  const api = buildModule({
    functions: ['rnResolveConflict'],
    prelude: `
      let _nbOwner = 'u1';
      let currentConfId = 'conf-a';
      const original = {
        id: 'n1', owner: 'u1', confId: 'conf-a', title: 'local', body: 'local-body',
        plainText: 'local', paperRefs: [], mediaIds: [], deleted: false,
        dirty: true, writeId: 'base', parentWriteId: 'base', baseBody: 'base',
      };
      const _nbNotes = new Map([[original.id, original]]);
      const _nb = {
        openId: 'n1', saveTimer: 123, baseWriteId: 'base', stale: true,
        lastSaved: { title: original.title, body: original.body },
      };
      const persisted = [];
      let releaseFirstPersist;
      let firstPersistStarted;
      const firstPersist = new Promise((resolve) => { firstPersistStarted = resolve; });
      const holdFirstPersist = new Promise((resolve) => { releaseFirstPersist = resolve; });
      let calls = 0;
      const nbPersist = async (rec) => {
        _nbNotes.set(rec.id, rec);
        persisted.push({ ...rec });
        calls++;
        if (calls === 1) {
          firstPersistStarted();
          await holdFirstPersist;
        }
        return true;
      };
      const nbFlush = async () => true;
      const rnFromServer = (id, raw, owner) => ({
        ...raw, id, owner, confId: currentConfId, dirty: false,
        parentWriteId: raw.writeId, baseBody: raw.body,
      });
      const rnSameContent = (a, b) => a.title === b.title && a.body === b.body && !!a.deleted === !!b.deleted;
      const rnMakeConflictCopy = (local, owner) => ({
        ...local, id: 'copy-1', owner, confId: currentConfId,
        title: local.title + ' (conflict copy)', writeId: null,
        parentWriteId: null, baseBody: null, dirty: true,
      });
      const rnCheckValid = () => true;
      const nbEnterMobileHistory = () => {};
      const nbHideBanner = () => {};
      const nbRenderRefs = () => {};
      const showToast = () => {};
      const t = (key) => key === 'nb_conflict' ? 'conflict {title}' : key;
      const titleEl = { value: original.title };
      const document = { getElementById: (id) => id === 'nb-title' ? titleEl : null };
      const clearTimeout = () => {};
    `,
    exports: `{
      run: () => rnResolveConflict('n1', {
        title: 'server', body: 'server-body', plainText: 'server', paperRefs: [],
        mediaIds: [], deleted: false, writeId: 'server-write',
      }),
      firstPersist,
      releaseFirstPersist,
      openId: () => _nb.openId,
      baseWriteId: () => _nb.baseWriteId,
      note: (id) => _nbNotes.get(id),
      simulateAutosave: () => {
        const id = _nb.openId;
        const cur = _nbNotes.get(id);
        _nbNotes.set(id, { ...cur, body: 'typed-during-conflict', dirty: true });
      },
      persisted: () => persisted,
    }`,
  });

  const resolving = api.run();
  await api.firstPersist;
  assert.equal(api.openId(), 'copy-1');
  assert.equal(api.baseWriteId(), null);

  api.simulateAutosave();
  api.releaseFirstPersist();
  await resolving;

  assert.equal(api.note('n1').body, 'server-body');
  assert.equal(api.note('n1').dirty, false);
  assert.equal(api.note('copy-1').body, 'typed-during-conflict');
  assert.equal(api.note('copy-1').dirty, true);
  assert.equal(api.persisted().filter((n) => n.id === 'copy-1').length, 1);
});

test('owner 강제 전환은 MediaRecorder onstop 뒤 녹음 정리까지 기다린다', async () => {
  const api = buildModule({
    functions: ['nbCloseEditor', 'nbRecStop', 'nbRecCancel'],
    prelude: `
      let resolveSettled;
      const settledPromise = new Promise((resolve) => { resolveSettled = resolve; });
      let stopped = false;
      const _nbRec = {
        active: true, finishing: false,
        recorder: { state: 'recording', stop: () => { stopped = true; } },
        stopTimer: null, finishPromise: Promise.resolve(), settledPromise,
      };
      const REC_STOP_FALLBACK_MS = 5000;
      const nbRecBusy = () => _nbRec.active || _nbRec.finishing;
      const nbRecFinish = () => Promise.resolve();
      const showToast = () => {};
      const t = (key) => key;
      const _nb = { openId: null };
    `,
    exports: `{
      run: () => nbCloseEditor({ flush: true, force: true }),
      release: () => { clearTimeout(_nbRec.stopTimer); _nbRec.stopTimer = null; resolveSettled(); },
      stopped: () => stopped,
    }`,
  });

  let closed = false;
  const closing = api.run().then(() => { closed = true; });
  await tick();

  assert.equal(api.stopped(), true);
  assert.equal(closed, false);

  api.release();
  await closing;
  assert.equal(closed, true);
});

test('MediaRecorder stop 누락 fallback도 녹음 lifecycle을 완료한다', async () => {
  const api = buildModule({
    functions: ['nbRecStop'],
    prelude: `
      const recorder = { state: 'recording', stop: () => {} };
      const _nbRec = { active: true, finishing: false, recorder, stopTimer: null, capHit: false };
      const REC_STOP_FALLBACK_MS = 5;
      let finishedWith = null;
      const nbRecFinish = (rec) => { finishedWith = rec; };
    `,
    exports: `{
      run: () => nbRecStop(false),
      finishedWithRecorder: () => finishedWith === recorder,
      clear: () => { clearTimeout(_nbRec.stopTimer); _nbRec.stopTimer = null; },
    }`,
  });

  api.run();
  await new Promise((resolve) => setTimeout(resolve, 15));
  assert.equal(api.finishedWithRecorder(), true);
  api.clear();
});

test('stop 이벤트가 없어도 강제 닫기는 fallback 뒤 완료된다', async () => {
  const api = buildModule({
    functions: ['nbRecElapsed', 'nbCloseEditor', 'nbRecStop', 'nbRecCancel', 'nbRecFinish'],
    prelude: `
      const events = [];
      let resolveSettled;
      const settledPromise = new Promise((resolve) => { resolveSettled = resolve; });
      const recorder = {
        state: 'recording',
        stop: () => { events.push('stop'); },
      };
      const _nbRec = {
        active: true, finishing: false, recorder, stream: null,
        chunks: [], bytes: 0, startedAt: 0, elapsedBefore: 0, paused: true,
        timer: null, stopTimer: null, persistTimer: null, cancelled: false,
        capHit: false, mime: 'audio/webm', token: 1, draftId: 'draft-1',
        noteId: 'note-1', owner: 'u1', confId: 'conf-a', persistedChunks: 0,
        persistPromise: Promise.resolve(), finishPromise: Promise.resolve(),
        settledPromise, resolveSettled,
      };
      const REC_STOP_FALLBACK_MS = 5;
      const nbRecBusy = () => _nbRec.active || _nbRec.finishing;
      const nbRecRenderPanel = () => {};
      const RecordingStore = {
        remove: async () => { events.push('remove'); },
      };
      const showToast = () => {};
      const t = (key) => key;
      const _nb = { openId: null };
    `,
    exports: `{
      run: () => nbCloseEditor({ flush: true, force: true }),
      active: () => _nbRec.active,
      events: () => events,
    }`,
  });

  await api.run();
  assert.equal(api.active(), false);
  assert.deepEqual(api.events(), ['stop', 'remove']);
});

test('늦게 도착한 이전 recorder 종료는 새 녹음을 건드리지 않는다', async () => {
  const api = buildModule({
    functions: ['nbRecFinish'],
    prelude: `
      const oldRecorder = {};
      const currentRecorder = {};
      const _nbRec = {
        active: true, finishing: false, recorder: currentRecorder, stream: null,
        chunks: [], bytes: 0, startedAt: 0, elapsedBefore: 0, paused: true,
        timer: null, stopTimer: null, persistTimer: null, cancelled: false,
        capHit: false, mime: 'audio/webm', token: 1, draftId: 'new-draft',
        noteId: 'new-note', owner: 'u1', confId: 'conf-a', persistedChunks: 0,
        persistPromise: Promise.resolve(), finishPromise: Promise.resolve(),
        settledPromise: Promise.resolve(), resolveSettled: null,
      };
    `,
    exports: `{
      run: () => nbRecFinish(oldRecorder),
      active: () => _nbRec.active,
      recorderUnchanged: () => _nbRec.recorder === currentRecorder,
    }`,
  });

  await api.run();
  assert.equal(api.active(), true);
  assert.equal(api.recorderUnchanged(), true);
});

test('녹음 취소는 진행 중인 draft 저장 뒤 임시본을 삭제한다', async () => {
  const api = buildModule({
    functions: ['nbRecElapsed', 'nbRecFinish'],
    prelude: `
      const events = [];
      let releasePut;
      const pendingPut = new Promise((resolve) => { releasePut = resolve; });
      const _nbRec = {
        active: true, finishing: false, recorder: null, stream: null,
        chunks: [new Blob(['audio'], { type: 'audio/webm' })], bytes: 5,
        startedAt: 0, elapsedBefore: 1200, paused: true,
        timer: null, stopTimer: null, cancelled: true, capHit: false, mime: 'audio/webm', token: 1,
        draftId: 'draft-1', noteId: 'note-1', owner: 'u1', confId: 'conf-a',
        persistTimer: null, persistedChunks: 1,
        persistPromise: pendingPut.then(() => { events.push('put-done'); }),
        finishPromise: Promise.resolve(), settledPromise: Promise.resolve(), resolveSettled: null,
      };
      const RecordingStore = {
        remove: async () => { events.push('remove'); },
      };
      const nbRecRenderPanel = () => {};
    `,
    exports: `{
      run: nbRecFinish,
      release: () => releasePut(),
      events: () => events,
    }`,
  });

  const finishing = api.run();
  await tick();
  assert.deepEqual(api.events(), []);

  api.release();
  await finishing;
  assert.deepEqual(api.events(), ['put-done', 'remove']);
});

test('최종 음성 저장이 실패해도 중단 복구 draft를 남긴다', async () => {
  const api = buildModule({
    functions: ['nbRecElapsed', 'nbRecDraftRow', 'nbRecPersistDraft', 'nbRecFinish'],
    prelude: `
      const events = [];
      let reported = null;
      const _nbRec = {
        active: true, finishing: false, recorder: null, stream: null,
        chunks: [new Blob(['audio'], { type: 'audio/webm' })], bytes: 5,
        startedAt: 0, elapsedBefore: 1200, paused: true,
        timer: null, stopTimer: null, cancelled: false, capHit: false, mime: 'audio/webm', token: 1,
        draftId: 'draft-1', noteId: 'note-1', owner: 'u1', confId: 'conf-a',
        persistTimer: null, persistedChunks: 0, persistPromise: Promise.resolve(),
        finishPromise: Promise.resolve(),
      };
      const RecordingStore = {
        put: async (row) => events.push(['draft-put', row.id, row.chunks.length]),
        remove: async (_owner, id) => events.push(['draft-remove', id]),
      };
      const MediaBackend = {
        put: async () => { events.push(['media-put']); throw new Error('quota'); },
      };
      const nbStorageEstimate = async () => true;
      const nbReportStorageError = (e) => { reported = e.message; };
      const nbRecRenderPanel = () => {};
      const nbNewId = () => 'media-1';
      const nbRequestPersist = () => {};
      const nbRun = () => true;
      const nbCollapseAfterNode = () => {};
      const nbToastOnce = () => {};
      const nbUpdateLocalBadge = () => {};
      const showToast = () => {};
      const t = (key) => key;
      const _nb = { openGen: 1, editor: {} };
    `,
    exports: `{
      run: nbRecFinish,
      events: () => events,
      reported: () => reported,
    }`,
  });

  await api.run();
  assert.deepEqual(api.events(), [
    ['draft-put', 'draft-1', 1],
    ['media-put'],
  ]);
  assert.equal(api.reported(), 'quota');
});

test('로컬 첨부는 참조가 끊긴 뒤 7일 동안 보존한다', async () => {
  const api = buildModule({
    functions: ['nbCleanupMedia'],
    prelude: `
      let now = 20 * 24 * 60 * 60 * 1000;
      const Date = { now: () => now };
      const NB_MEDIA_GRACE_MS = 7 * 24 * 60 * 60 * 1000;
      const _nbOwner = 'u1';
      const saved = [];
      const removed = [];
      let stamped = null;
      const MetaStore = {
        get: async () => 0,
        put: async (_key, value) => { stamped = value; },
      };
      const NoteStore = {
        listOwner: async () => [{ mediaIds: ['live'] }],
      };
      const nbCleanIds = (ids) => ids;
      const MediaBackend = {
        list: async () => [
          { id: 'live', orphanedAt: now - 10 * 24 * 60 * 60 * 1000 },
          { id: 'new-orphan', orphanedAt: 0, createdAt: 1 },
          { id: 'recent-orphan', orphanedAt: now - 6 * 24 * 60 * 60 * 1000 },
          { id: 'expired-orphan', orphanedAt: now - 8 * 24 * 60 * 60 * 1000 },
        ],
        save: async (row) => saved.push(row),
        remove: async (_owner, id) => removed.push(id),
      };
    `,
    exports: `{
      run: () => nbCleanupMedia('u1'),
      saved: () => saved,
      removed: () => removed,
      stamped: () => stamped,
      now: () => now,
    }`,
  });

  assert.equal(await api.run(), 1);
  assert.deepEqual(api.removed(), ['expired-orphan']);
  assert.equal(api.saved().find((r) => r.id === 'live').orphanedAt, 0);
  assert.equal(api.saved().find((r) => r.id === 'new-orphan').orphanedAt, api.now());
  assert.equal(api.stamped(), api.now());
});

test('richNotes 경계와 Firestore 규칙의 데이터 보호 계약이 유지된다', () => {
  const richStart = indexHtml.indexOf('// ====== 노트 (리치 노트) ======');
  const richEnd = indexHtml.indexOf('// ====== Buttons ======', richStart);
  assert.ok(richStart >= 0 && richEnd > richStart);
  const richSection = indexHtml.slice(richStart, richEnd)
    .replace(/\/\/.*$/gm, '')
    .replace(/\/\*[\s\S]*?\*\//g, '');

  assert.doesNotMatch(richSection, /\btouch\s*\(/);
  assert.doesNotMatch(indexHtml, /signInWithRedirect|getRedirectResult/);
  assert.match(indexHtml, /window\.addEventListener\('popstate'/);
  assert.match(indexHtml, /history\.pushState\(/);

  const conflictSource = extractFunction('rnResolveConflict');
  assert.match(conflictSource, /_nbNotes\.set\(copy\.id, copy\);[\s\S]*_nb\.openId = copy\.id;[\s\S]*await nbPersist\(copyToPersist\);/);

  assert.match(rules, /match \/users\/\{uid\}\/confs\/\{confId\}/);
  assert.match(rules, /match \/richNotes\/\{noteId\}/);
  assert.match(rules, /d\.body\.toUtf8\(\)\.size\(\) <= 614400/);
  assert.match(rules, /request\.resource\.data\.parentWriteId == resource\.data\.writeId/);
  assert.match(rules, /request\.resource\.data\.createdAt == resource\.data\.createdAt/);
  assert.match(rules, /allow delete: if false/);
  assert.doesNotMatch(rules, /match \/users\/\{uid\}\/\{document=\*\*\}/);
});

test('내 일정은 별점과 빠른 메모 입력 대신 문서 노트 진입점만 렌더한다', () => {
  const source = extractFunction('renderItinerary');
  assert.match(source, /nbPickEntryHtml\(it\.key\)/);
  assert.doesNotMatch(source, /note-input|class="rating|clear_rating|note_ph/);
  assert.doesNotMatch(indexHtml, /data-nact="promote"|nb_promote/);
});

test('레거시 별점과 빠른 메모는 로컬 payload와 원격 수신에서 보존된다', () => {
  const local = buildModule({
    functions: ['buildLocalItems'],
    prelude: `
      const state = {
        selected: new Set(['s1#p1']),
        notes: new Map([['s1#p1', { rating: 4, note: 'legacy memo', must: true }]]),
        stamps: new Map([['s1#p1', 42]]),
      };
    `,
    exports: `{ run: buildLocalItems }`,
  });
  assert.deepEqual(local.run(), {
    's1#p1': { s: 1, r: 4, n: 'legacy memo', m: 1, t: 42 },
  });

  const remote = buildModule({
    functions: ['applyRemoteItems'],
    prelude: `
      const state = { selected: new Set(), notes: new Map(), stamps: new Map() };
      const saveSelection = () => {};
      const saveNotes = () => {};
      const saveStamps = () => {};
      const rerenderAfterRemoteChange = () => {};
    `,
    exports: `{
      run: applyRemoteItems,
      note: (key) => state.notes.get(key),
      stamp: (key) => state.stamps.get(key),
    }`,
  });
  assert.equal(remote.run({ 's1#p1': { s: 0, r: 3, n: 'old client memo', m: 0, t: 7 } }), 1);
  assert.deepEqual(remote.note('s1#p1'), { rating: 3, note: 'old client memo', must: false });
  assert.equal(remote.stamp('s1#p1'), 7);
});

test('꼭 듣기 변경은 보존된 별점과 빠른 메모를 지우지 않는다', () => {
  const api = buildModule({
    functions: ['getNote', 'setNote', 'isMust', 'toggleMust', 'clearMustOnDeselect'],
    prelude: `
      const state = {
        selected: new Set(),
        notes: new Map([['s1#p1', { rating: 5, note: 'keep me', must: false }]]),
      };
      let touches = 0;
      const saveNotes = () => {};
      const saveSelection = () => {};
      const touch = () => { touches++; };
    `,
    exports: `{
      toggle: toggleMust,
      clear: clearMustOnDeselect,
      note: (key) => state.notes.get(key),
      touches: () => touches,
    }`,
  });

  assert.equal(api.toggle('s1#p1'), true);
  assert.deepEqual(api.note('s1#p1'), { rating: 5, note: 'keep me', must: true });
  api.clear('s1#p1');
  assert.deepEqual(api.note('s1#p1'), { rating: 5, note: 'keep me', must: false });
  assert.equal(api.touches(), 2);
});

test('발표별 노트 진입은 기존 노트, 레거시 메모, 빈 노트를 구분한다', async () => {
  const api = buildModule({
    functions: ['nbOpenPaperEntry'],
    prelude: `
      const _nbEntryPending = new Set();
      let linked = [];
      let memo = '';
      const calls = [];
      const nbNotesForPaper = () => linked;
      const getNote = () => ({ rating: 0, note: memo, must: false });
      const nbOpenForPaper = async () => { calls.push('open'); return 'opened'; };
      const nbPromoteQuickNote = async () => { calls.push('promote'); return 'promoted'; };
      const nbCreateForPaper = async () => { calls.push('create'); return 'created'; };
    `,
    exports: `{
      run: nbOpenPaperEntry,
      setLinked: (v) => { linked = v; },
      setMemo: (v) => { memo = v; },
      calls: () => calls,
    }`,
  });

  api.setLinked([{ id: 'n1' }]);
  api.setMemo('legacy');
  assert.equal(await api.run('s1#p1'), 'opened');

  api.setLinked([]);
  assert.equal(await api.run('s1#p1'), 'promoted');

  api.setMemo('');
  assert.equal(await api.run('s1#p1'), 'created');
  assert.deepEqual(api.calls(), ['open', 'promote', 'create']);

  const source = extractFunction('nbOpenPaperEntry') + extractFunction('nbPromoteQuickNote');
  assert.doesNotMatch(source, /\bsetNote\s*\(|\btouch\s*\(/);
});

test('발표에 연결된 노트 하나는 바로 열고 여러 개는 발표별 목록을 연다', async () => {
  const api = buildModule({
    functions: ['nbOpenForPaper'],
    prelude: `
      let linked = [];
      let opened = null;
      let created = 0;
      let rendered = 0;
      let view = '';
      const _nbUi = { filter: 'all', paperKey: null };
      const document = { getElementById: () => null };
      const nbNotesForPaper = () => linked;
      const nbCreateForPaper = async () => { created++; };
      const setView = (v) => { view = v; };
      const nbOpenNote = async (id) => { opened = id; };
      const renderNotesList = () => { rendered++; };
    `,
    exports: `{
      run: nbOpenForPaper,
      setLinked: (v) => { linked = v; },
      state: () => ({ opened, created, rendered, view, paperKey: _nbUi.paperKey }),
    }`,
  });

  api.setLinked([]);
  await api.run('s1#p1');
  assert.equal(api.state().created, 1);

  api.setLinked([{ id: 'n1' }]);
  await api.run('s1#p1');
  assert.equal(api.state().opened, 'n1');

  api.setLinked([{ id: 'n1' }, { id: 'n2' }]);
  await api.run('s1#p1');
  assert.equal(api.state().rendered, 1);
  assert.equal(api.state().view, 'notes');
  assert.equal(api.state().paperKey, 's1#p1');
});

test('CSV와 ICS는 보존된 별점과 빠른 메모를 계속 내보낸다', () => {
  assert.match(indexHtml, /if \(n\.rating\) descParts\.push\('Rating: '/);
  assert.match(indexHtml, /if \(n\.note\)\s+descParts\.push\('Notes: '/);
  assert.match(indexHtml, /'MustSee','Rating','Notes','LinkedNoteTitles','LinkedNoteText'/);
  assert.match(indexHtml, /n\.rating \|\| ''[\s\S]*n\.note \|\| ''/);
});
