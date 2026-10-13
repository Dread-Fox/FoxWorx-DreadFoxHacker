# Mobile terminal scrolling verification

Verified on 2026-10-12 with offline Chromium fixtures and the bundled xterm.
No terminal commands or external target traffic were executed by the browser checks.

- `tests/browser_terminal_scroll.py`: passed at 320px, 390px and 1600px. Checks mouse and actual browser touch dragging, keyboard navigation, vertical terminal swipes without outer-page scrolling, retained history position when output arrives, jump to latest, alternate-buffer switching, and session reset. Mobile slider and latest button have targets at least 44px high.
- `tests/browser_smoke.py`: passed with no JavaScript errors. The full app initializes the controls, scrolling changes the real terminal buffer, latest returns to the bottom, and history controls remain within the terminal view after mobile resizing. The resized pane contains the newest output; there is no horizontal overflow.
- `scripts/test.sh`: 279 passed, 1 skipped. Python compilation, shell script syntax and JavaScript syntax checks passed. One dependency deprecation warning from Starlette/AnyIO remains.
- `node --check static/terminal-scroll.js`: passed.

Chromium and the full suite were run outside the restricted sandbox because browser startup and some local socket/subprocess tests are blocked inside it. Phone-sized browser checks are not a physical iOS/Android device test. No live service was restarted or deployed.
