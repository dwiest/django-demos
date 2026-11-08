import { colorTags } from './tags.js';
import { initEditor } from './editor.js';
import { initList } from './list.js';
colorTags();
const editor = document.querySelector('[data-editor]');
if (editor) initEditor(editor);
initList();
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') document.querySelectorAll('details[open]').forEach(details => details.open = false);
});
