// Saves text as a file made in the page. The text is never rendered here.
import { h } from './dom.js';

export function saveText(text, fileName, type = 'text/plain') {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = h('a', { href: url, download: fileName, hidden: '' });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
