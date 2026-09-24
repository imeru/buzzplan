// 최상위 블록(문단, 제목, 목록, 표, 이미지 등 doc의 직계 자식) 하나를 통째로
// 앞/뒤 형제와 자리바꿈하는 명령. Tiptap/ProseMirror 공식 확장에는 없는 동작이라
// prosemirror-model의 Fragment API만으로 직접 구현했다 (외부 비공식 패키지 없음).
import { Extension } from '@tiptap/core';
import { Fragment } from '@tiptap/pm/model';
import { TextSelection } from '@tiptap/pm/state';

// doc의 직계 자식 중 index번째 노드의 시작 오프셋과 노드를 찾는다.
function childAt(doc, index) {
  let start = null;
  let node = null;
  doc.forEach((child, offset, i) => {
    if (i === index) {
      start = offset;
      node = child;
    }
  });
  return { start, node };
}

// doc의 직계 자식 loIndex와 loIndex+1을 서로 맞바꾼다. focusIndex는 자리바꿈 후에도
// 커서를 따라가야 할 노드가 원래 loIndex였는지 loIndex+1이었는지를 가리킨다.
function swapAdjacentTopLevelBlocks(state, dispatch, loIndex, focusIndex) {
  const { doc } = state;
  if (loIndex < 0 || loIndex + 1 >= doc.childCount) return false;

  const a = childAt(doc, loIndex); // 원래 앞쪽
  const b = childAt(doc, loIndex + 1); // 원래 뒤쪽
  if (a.node == null || b.node == null) return false;

  if (dispatch) {
    const from = a.start;
    const to = b.start + b.node.nodeSize;
    const swapped = Fragment.from([b.node, a.node]);
    const tr = state.tr.replaceWith(from, to, swapped);

    // 이동한 블록 내부에 커서를 다시 놓는다.
    // 자리바꿈 후 새 배치는 [b.node, a.node] 순서다(b가 from, a가 from + b.node.nodeSize).
    // focusIndex가 loIndex와 같으면 원래 loIndex에 있던 a가 대상이고, 자리바꿈 후에는
    // 뒤쪽(from + b.node.nodeSize)에 놓인다. 이 두 삼항의 짝을 거꾸로 쓰면 커서가
    // 엉뚱한 형제 블록에 남아, 그다음 이동 명령이 잘못된 블록을 움직이게 된다.
    const movedNode = focusIndex === loIndex ? a.node : b.node;
    const movedStart = focusIndex === loIndex ? from + b.node.nodeSize : from;
    const insidePos = Math.min(movedStart + 1, tr.doc.content.size);
    const $pos = tr.doc.resolve(insidePos);
    tr.setSelection(TextSelection.near($pos));

    dispatch(tr.scrollIntoView());
  }
  return true;
}

export const MoveBlock = Extension.create({
  name: 'moveBlock',

  addCommands() {
    return {
      moveBlockUp:
        () =>
        ({ state, dispatch }) => {
          const index = state.selection.$from.index(0);
          if (index <= 0) return false;
          return swapAdjacentTopLevelBlocks(state, dispatch, index - 1, index);
        },
      moveBlockDown:
        () =>
        ({ state, dispatch }) => {
          const index = state.selection.$from.index(0);
          if (index >= state.doc.childCount - 1) return false;
          return swapAdjacentTopLevelBlocks(state, dispatch, index, index);
        },
    };
  },
});

export default MoveBlock;
