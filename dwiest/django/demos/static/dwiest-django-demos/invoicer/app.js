document.addEventListener('DOMContentLoaded', () => {
  const search = document.querySelector('#invoice-search');
  if (search) search.addEventListener('input', () => {
    let count = 0;
    document.querySelectorAll('#invoice-list tbody tr').forEach(row => {
      row.hidden = !row.textContent.toLowerCase().includes(search.value.toLowerCase());
      if (!row.hidden) count++;
    });
    document.querySelector('#search-empty').hidden = count > 0;
  });
  const editor = document.querySelector('#invoice-editor');
  if (!editor) return;
  const calculate = () => {
    let hours = 0, cents = 0;
    editor.querySelectorAll('.line-item').forEach(row => {
      if (row.querySelector('[name$="-DELETE"]')?.checked) return;
      const quantity = Number(row.querySelector('[name$="-quantity"]')?.value || 0);
      const rate = Number(row.querySelector('[name$="-rate"]')?.value || 0);
      // Blank extra forms are not invoice entries.
      const description = row.querySelector('[name$="-description"]')?.value.trim();
      const date = row.querySelector('[name$="-date"]')?.value;
      if (!description && !date && !row.querySelector('[name$="-id"]')?.value) return;
      hours += quantity;
      cents += Math.round(quantity * rate * 100);
    });
    document.querySelector('#amount').textContent = `${hours.toFixed(2)} hours · ${new Intl.NumberFormat('en-US', {style:'currency',currency:'USD'}).format(cents / 100)}`;
  };
  editor.addEventListener('input', calculate);
  editor.addEventListener('change', calculate);
  calculate();
});
