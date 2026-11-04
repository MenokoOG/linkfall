// DOM helpers. Text always goes in as text (textContent or a text node), never as HTML, so a
// model's or an enemy's words cannot become markup (ASVS 3.2.2).
export function byId(id) {
  const element = document.getElementById(id);
  if (!element) throw new Error(`The page has no element with id "${id}".`);
  return element;
}

export function setText(element, text) {
  element.textContent = text;
}

export function clear(element) {
  element.replaceChildren();
}

// h('div', { class: 'gauge', 'data-tone': 'cyan' }, 'text', otherElement)
export function h(tag, attributes = {}, ...children) {
  const element = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) {
    if (value !== undefined && value !== null) element.setAttribute(name, String(value));
  }
  for (const child of children) {
    element.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return element;
}
