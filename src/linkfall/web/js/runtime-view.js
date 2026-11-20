// The hosted copy's start-up status: progress while Python loads, then a standing note, or an
// error with a retry and the command to run it locally. Text only, through h().
import { h, setText } from './dom.js';

export const LOCAL_COMMAND = 'docker compose -f compose.scripted.yaml up';
export const READY_TEXT = 'Running in your browser with the scripted crew. A run lasts until you reload the page.';

export const progressText = (step, total, label) => `Starting LINKFALL in your browser, step ${step} of ${total}: ${label}.`;
export const failureText = (message) => `${message} To run it on your own machine instead: ${LOCAL_COMMAND}`;

export function createRuntimeStatus(container = document.querySelector('main') ?? document.body) {
  const text = h('span', {}, '');
  const box = h('div', { class: 'banner', role: 'status' }, text);
  container.prepend(box);
  return {
    progress: (step, total, label) => setText(text, progressText(step, total, label)),
    ready() {
      box.setAttribute('data-tone', 'ok');
      setText(text, READY_TEXT);
    },
    failed(message, onRetry) {
      box.setAttribute('role', 'alert');
      setText(text, failureText(message));
      const retry = h('button', { class: 'btn', type: 'button' }, 'Try again');
      retry.addEventListener('click', onRetry);
      box.append(retry);
    },
  };
}
