// firestore.rules 실행 검증. 로컬 Firestore 에뮬레이터와 demo 프로젝트만 쓰므로 실제 buzzplan
// 프로젝트와 데이터에 닿지 않는다. 실행: npm run test:rules (Java 21 이상 필요)
import fs from 'node:fs';
import { initializeTestEnvironment, assertSucceeds, assertFails } from '@firebase/rules-unit-testing';
import {
  doc, getDoc, setDoc, updateDoc, deleteDoc, collection, getDocs,
  serverTimestamp, Timestamp, runTransaction,
} from 'firebase/firestore';

const RULES = fs.readFileSync(new URL('../../firestore.rules', import.meta.url), 'utf8');
const env = await initializeTestEnvironment({
  projectId: 'demo-buzzplan',
  firestore: { rules: RULES, host: '127.0.0.1', port: 8089 },
});

const ME = 'alice', OTHER = 'mallory', CONF = 'roomvent-2026';
const mine = env.authenticatedContext(ME).firestore();
const other = env.authenticatedContext(OTHER).firestore();
const anon = env.unauthenticatedContext().firestore();

const parent = (db, uid = ME) => doc(db, 'users', uid, 'confs', CONF);
const note = (db, id, uid = ME) => doc(db, 'users', uid, 'confs', CONF, 'richNotes', id);

// index.html rnPayload와 같은 모양
function payload(over = {}) {
  return {
    v: 1, title: '노트', body: JSON.stringify({ type: 'doc', content: [{ type: 'paragraph' }] }),
    plainText: '본문', paperRefs: [{ key: 'S1#S1-1', title: '발표' }], mediaIds: ['m1'],
    writeId: 'w1', parentWriteId: null, deleted: false,
    createdAt: serverTimestamp(), updatedAt: serverTimestamp(), ...over,
  };
}

const results = [];
async function check(name, expect, fn) {
  try {
    await (expect === 'allow' ? assertSucceeds(fn()) : assertFails(fn()));
    results.push(['ok  ', expect, name]);
  } catch (e) {
    results.push(['FAIL', expect, name + '  :: ' + String(e && e.message || e).slice(0, 160)]);
  }
}

// ---------- 기존 일정 문서 (구버전 앱 호환) ----------
await check('본인 부모 문서 생성(set)', 'allow', () =>
  setDoc(parent(mine), { items: { 'S1#S1-1': { s: 1, r: 0, n: '', m: 0, t: 1 } }, updatedAt: serverTimestamp() }));
await check('본인 부모 문서 통째 덮어쓰기(set)', 'allow', () =>
  setDoc(parent(mine), { items: { 'S1#S1-1': { s: 1, r: 4, n: '메모', m: 1, t: 2 } }, updatedAt: serverTimestamp() }));
await check('본인 부모 문서 읽기', 'allow', () => getDoc(parent(mine)));
await check('본인 confs 목록 조회(checkOtherConfs)', 'allow', () => getDocs(collection(mine, 'users', ME, 'confs')));
await check('남의 부모 문서 읽기', 'deny', () => getDoc(parent(other, ME)));
await check('남의 부모 문서 쓰기', 'deny', () => setDoc(parent(other, ME), { items: {} }));
await check('비로그인 부모 문서 읽기', 'deny', () => getDoc(parent(anon, ME)));
await check('users/<uid> 아래 다른 경로 쓰기', 'deny', () => setDoc(doc(mine, 'users', ME, 'misc', 'x'), { a: 1 }));

// ---------- richNotes 생성 ----------
await check('노트 생성 (앱 payload)', 'allow', () => setDoc(note(mine, 'n1'), payload()));
await check('노트 읽기', 'allow', () => getDoc(note(mine, 'n1')));
await check('노트 목록 조회', 'allow', () => getDocs(collection(mine, 'users', ME, 'confs', CONF, 'richNotes')));
await check('남이 내 노트 읽기', 'deny', () => getDoc(note(other, 'n1', ME)));
await check('남이 내 경로에 노트 생성', 'deny', () => setDoc(note(other, 'x1', ME), payload()));
await check('생성인데 parentWriteId 있음', 'deny', () => setDoc(note(mine, 'n2'), payload({ parentWriteId: 'w0' })));
await check('필드 누락(mediaIds)', 'deny', () => { const p = payload(); delete p.mediaIds; return setDoc(note(mine, 'n3'), p); });
await check('필드 추가(extra)', 'deny', () => setDoc(note(mine, 'n4'), payload({ extra: 1 })));
await check('클라이언트 시각으로 createdAt', 'deny', () => setDoc(note(mine, 'n5'), payload({ createdAt: Timestamp.fromMillis(1) })));
await check('v가 2', 'deny', () => setDoc(note(mine, 'n6'), payload({ v: 2 })));
await check('제목 200자', 'allow', () => setDoc(note(mine, 'n7'), payload({ title: '가'.repeat(200) })));
await check('제목 201자', 'deny', () => setDoc(note(mine, 'n8'), payload({ title: '가'.repeat(201) })));
await check('본문 한글 204800자 = 614400바이트', 'allow', () => setDoc(note(mine, 'n9'), payload({ body: '가'.repeat(204800) })));
await check('본문 한글 204801자 = 614403바이트', 'deny', () => setDoc(note(mine, 'n10'), payload({ body: '가'.repeat(204801) })));
await check('plainText 4097자', 'deny', () => setDoc(note(mine, 'n11'), payload({ plainText: 'a'.repeat(4097) })));
await check('paperRefs 101개', 'deny', () => setDoc(note(mine, 'n12'), payload({ paperRefs: Array.from({ length: 101 }, (_, i) => ({ key: 'k' + i, title: 't' })) })));
await check('mediaIds 51개', 'deny', () => setDoc(note(mine, 'n13'), payload({ mediaIds: Array.from({ length: 51 }, (_, i) => 'm' + i) })));
await check('mediaIds 50개', 'allow', () => setDoc(note(mine, 'n14'), payload({ mediaIds: Array.from({ length: 50 }, (_, i) => 'm' + i) })));

// ---------- richNotes 갱신 ----------
const created = (await getDoc(note(mine, 'n1'))).data().createdAt;
await check('정상 갱신 (체인 w1→w2)', 'allow', () =>
  setDoc(note(mine, 'n1'), payload({ writeId: 'w2', parentWriteId: 'w1', createdAt: created, title: '수정' })));
await check('옛 부모로 갱신 (w1 기준, 서버는 w2)', 'deny', () =>
  setDoc(note(mine, 'n1'), payload({ writeId: 'w3', parentWriteId: 'w1', createdAt: created })));
await check('writeId를 바꾸지 않은 갱신', 'deny', () =>
  setDoc(note(mine, 'n1'), payload({ writeId: 'w2', parentWriteId: 'w2', createdAt: created })));
await check('createdAt 변경', 'deny', () =>
  setDoc(note(mine, 'n1'), payload({ writeId: 'w3', parentWriteId: 'w2', createdAt: Timestamp.fromMillis(5) })));
await check('parentWriteId 생략한 갱신(null)', 'deny', () =>
  setDoc(note(mine, 'n1'), payload({ writeId: 'w3', parentWriteId: null, createdAt: created })));
await check('부분 갱신(updateDoc title만)', 'deny', () => updateDoc(note(mine, 'n1'), { title: 'x' }));
await check('앱 방식 transaction 갱신 (get 후 set, w2→w3)', 'allow', () =>
  runTransaction(mine, async (tx) => {
    const s = await tx.get(note(mine, 'n1'));
    tx.set(note(mine, 'n1'), payload({ writeId: 'w3', parentWriteId: s.data().writeId, createdAt: s.data().createdAt }));
  }));
await check('휴지통 tombstone (deleted=true, w3→w4)', 'allow', () =>
  setDoc(note(mine, 'n1'), payload({ writeId: 'w4', parentWriteId: 'w3', createdAt: created, deleted: true })));
await check('복원 (deleted=false, w4→w5)', 'allow', () =>
  setDoc(note(mine, 'n1'), payload({ writeId: 'w5', parentWriteId: 'w4', createdAt: created, deleted: false })));
await check('노트 영구 삭제', 'deny', () => deleteDoc(note(mine, 'n1')));

// ---------- 구버전 앱이 부모를 덮어써도 노트 유지 ----------
await setDoc(parent(mine), { items: {} });
await check('부모 덮어쓴 뒤에도 노트 남음', 'allow', async () => {
  const s = await getDoc(note(mine, 'n1'));
  if (!s.exists() || s.data().writeId !== 'w5') throw new Error('note lost');
});

await env.cleanup();
for (const r of results) console.log(r.join('  '));
const fails = results.filter(r => r[0] === 'FAIL').length;
console.log(`\n${results.length - fails}/${results.length} passed`);
process.exit(fails ? 1 : 0);
