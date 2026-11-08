// Shared tag presentation; no raw legacy CSS is injected into the new UI.
export function tone(name) {
  return String([...name.toLowerCase()].reduce((sum, char) => (sum * 31 + char.codePointAt(0)) >>> 0, 0) % 6);
}
export function colorTags(root = document) {
  root.querySelectorAll('[data-tag-name]').forEach(tag => tag.dataset.tone = tone(tag.dataset.tagName));
}
export function initTagPicker(picker) {
  const choices = [...picker.querySelectorAll('input[type=checkbox]')];
  const selected = picker.querySelector('[data-selected-tags]');
  const label = input => input.closest('label').textContent.trim();
  const refresh = () => {
    selected.replaceChildren();
    choices.filter(input => input.checked).forEach(input => {
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'tag';
      button.dataset.tagName = label(input); button.dataset.tone = tone(label(input));
      button.textContent = `${label(input)} ×`;
      button.setAttribute('aria-label', `Remove tag ${label(input)}`);
      button.addEventListener('click', () => { input.checked = false; input.dispatchEvent(new Event('change', { bubbles: true })); });
      selected.append(button);
    });
  };
  picker.addEventListener('change', refresh);
  picker.querySelector('[data-tag-search]').addEventListener('input', event => {
    const term = event.target.value.toLowerCase().trim();
    choices.forEach(input => input.closest('.tag-option').hidden = !label(input).toLowerCase().includes(term));
    picker.querySelector('[data-no-tags]').hidden = choices.some(input => !input.closest('.tag-option').hidden);
  });
  refresh();
  return refresh;
}
