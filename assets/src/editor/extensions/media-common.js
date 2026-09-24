// localImage/localAudio 노드가 공유하는 mediaId 해석 로직.
//
// 노드 자체는 실제 파일을 들고 있지 않고 mediaId 문자열만 doc JSON에 저장한다.
// 실제 바이트(사진, 녹음)를 어디에 두느냐(IndexedDB, Firestore Storage 등)는
// 이 번들의 책임이 아니고, 호스트(index.html)가 createEditor(el, { resolveMedia })로
// 넘겨주는 resolver 함수의 책임이다. resolver가 없거나 실패하면 노드는 자리표시자를
// 보여줄 뿐 편집 자체는 막지 않는다 (미해결 통합 지점을 화면에서 바로 드러내기 위함).
export function resolveMediaInto({ resolveMedia, mediaId, kind, onResolved, onError }) {
  if (!mediaId || typeof resolveMedia !== 'function') {
    return { cancel() {} };
  }

  let cancelled = false;
  let cleanup = null;

  Promise.resolve()
    .then(() => resolveMedia(mediaId, { kind }))
    .then((result) => {
      if (cancelled) {
        if (result && typeof result.revoke === 'function') result.revoke();
        return;
      }
      if (!result || !result.url) {
        onError(new Error('resolveMedia는 { url } 을 반환해야 합니다'));
        return;
      }
      cleanup = typeof result.revoke === 'function' ? result.revoke : null;
      onResolved(result.url);
    })
    .catch((err) => {
      if (!cancelled) onError(err instanceof Error ? err : new Error(String(err)));
    });

  return {
    cancel() {
      cancelled = true;
      if (cleanup) cleanup();
    },
  };
}

export function placeholderText(mediaId, kind, customText) {
  if (typeof customText === 'function') return String(customText(mediaId, { kind }));
  if (customText) return String(customText);
  const kindLabel = kind === 'audio' ? '오디오' : '이미지';
  return `[${kindLabel} 준비 중: ${mediaId || '(mediaId 없음)'}]`;
}
