// Use xterm's public buffer API so the control follows swipes, wheel input,
// output, resizing, session resets, and fullscreen terminal applications.
export function bindTerminalScroll(term) {
  const slider = document.getElementById('terminal-scroll');
  const latest = document.getElementById('terminal-latest');
  const status = document.getElementById('terminal-scroll-status');
  document.getElementById('terminal-scroll-controls').hidden = false;

  function sync() {
    const buffer = term.buffer.active;
    const normal = buffer.type === 'normal';
    slider.max = String(buffer.baseY);
    slider.value = String(buffer.viewportY);
    slider.disabled = !normal || buffer.baseY === 0;
    latest.disabled = !normal || buffer.viewportY === buffer.baseY;
    status.textContent = !normal ? 'Fullscreen program · history unavailable'
      : buffer.viewportY === buffer.baseY ? 'Latest output'
      : `Reading older output · ${buffer.baseY - buffer.viewportY} lines above latest`;
    slider.setAttribute('aria-valuetext', status.textContent);
  }

  slider.addEventListener('input', () => {
    if (term.buffer.active.type === 'normal') {
      term.scrollToLine(Number(slider.value));
      sync();
    }
  });
  latest.addEventListener('click', () => {
    term.scrollToBottom();
    sync();
    // Keep focus on the control: scrolling must not open the phone keyboard.
  });
  term.onScroll(sync);
  term.onWriteParsed(sync);
  term.onResize(sync);
  term.buffer.onBufferChange(sync);
  sync();
}
