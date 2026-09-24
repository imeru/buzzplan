// 툴바 버튼 하나당 함수 하나가 되도록 다듬은 커맨드 래퍼.
// 전부 editor.chain().focus()....run() 을 감싸고 boolean(성공 여부)을 돌려준다.
// 여기 없는 동작(표 안 행/열 세부 조작 등)은 handle.run(name, ...args)로
// editor.commands[name](...args)를 직접 호출할 수 있다 (탈출구).
export function createCommandApi(editor) {
  const run = (fn) => {
    if (editor.isDestroyed) return false;
    return fn(editor.chain().focus());
  };

  return {
    // 제목 / 문단
    toggleHeading: (level = 2) => run((c) => c.toggleHeading({ level }).run()),
    setParagraph: () => run((c) => c.setParagraph().run()),

    // 목록
    toggleBulletList: () => run((c) => c.toggleBulletList().run()),
    toggleOrderedList: () => run((c) => c.toggleOrderedList().run()),
    toggleTaskList: () => run((c) => c.toggleTaskList().run()),

    // 인라인 서식
    toggleBold: () => run((c) => c.toggleBold().run()),
    toggleItalic: () => run((c) => c.toggleItalic().run()),
    toggleUnderline: () => run((c) => c.toggleUnderline().run()),
    toggleStrike: () => run((c) => c.toggleStrike().run()),

    // 글꼴 / 글자 크기 / 색 / 형광펜
    setFontFamily: (family) => run((c) => c.setFontFamily(family).run()),
    unsetFontFamily: () => run((c) => c.unsetFontFamily().run()),
    setFontSize: (size) => run((c) => c.setFontSize(size).run()),
    unsetFontSize: () => run((c) => c.unsetFontSize().run()),
    setColor: (color) => run((c) => c.setColor(color).run()),
    unsetColor: () => run((c) => c.unsetColor().run()),
    toggleHighlight: (color) => run((c) => c.toggleHighlight(color ? { color } : undefined).run()),
    unsetHighlight: () => run((c) => c.unsetHighlight().run()),

    // 링크
    setLink: (href, opts = {}) =>
      run((c) => (href ? c.setLink({ href, ...opts }).run() : c.unsetLink().run())),
    unsetLink: () => run((c) => c.unsetLink().run()),

    // 표
    insertTable: (rows = 3, cols = 3, withHeaderRow = true) =>
      run((c) => c.insertTable({ rows, cols, withHeaderRow }).run()),
    addColumnBefore: () => run((c) => c.addColumnBefore().run()),
    addColumnAfter: () => run((c) => c.addColumnAfter().run()),
    deleteColumn: () => run((c) => c.deleteColumn().run()),
    addRowBefore: () => run((c) => c.addRowBefore().run()),
    addRowAfter: () => run((c) => c.addRowAfter().run()),
    deleteRow: () => run((c) => c.deleteRow().run()),
    deleteTable: () => run((c) => c.deleteTable().run()),

    // 코드 블록
    toggleCodeBlock: () => run((c) => c.toggleCodeBlock().run()),

    // 되돌리기 / 다시하기
    undo: () => run((c) => c.undo().run()),
    redo: () => run((c) => c.redo().run()),

    // 최상위 블록 이동
    moveBlockUp: () => run((c) => c.moveBlockUp().run()),
    moveBlockDown: () => run((c) => c.moveBlockDown().run()),

    // 로컬 미디어 (mediaId 계약은 extensions/local-image.js, local-audio.js 참고)
    insertLocalImage: (mediaId, attrs = {}) =>
      run((c) => c.insertLocalImage({ mediaId, ...attrs }).run()),
    insertLocalAudio: (mediaId, attrs = {}) =>
      run((c) => c.insertLocalAudio({ mediaId, ...attrs }).run()),

    // 탈출구: 여기 없는 임의의 등록된 명령을 이름으로 직접 실행한다.
    run: (name, ...args) => {
      if (editor.isDestroyed) return false;
      const chain = editor.chain().focus();
      if (typeof chain[name] !== 'function') return false;
      return chain[name](...args).run();
    },
  };
}

export default createCommandApi;
