"""Offline mobile scroll checks with real xterm; no shell or network traffic.

Run with the project's Python interpreter (optional Playwright + Chromium).
"""
from pathlib import Path
import re

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def run():
    html = (ROOT / 'static/index.html').read_text()
    html = re.sub(r'<script\b[^>]*>.*?</script>', '', html, flags=re.S)
    component = ROOT / 'static/terminal-scroll.js'
    binding = (
        "import {bindTerminalScroll} from './static/terminal-scroll.js';"
        if component.exists() else ''
    )
    html += '''<script type="module">
    import bundle from './static/vendor/xterm-bundle.js';
    ''' + binding + '''
    document.getElementById('login-screen').hidden=true;
    document.getElementById('workbench').hidden=false;
    document.getElementById('terminal-empty').hidden=true;
    const host=document.getElementById('terminal');host.hidden=false;
    window.term=new bundle.Terminal({scrollback:3000,rows:18,cols:30});
    term.open(host);
    ''' + ('bindTerminalScroll(term);' if component.exists() else '') + '''
    window.write=text=>new Promise(resolve=>term.write(text,resolve));
    window.ready=true;
    </script>'''

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True,
                                    args=['--no-sandbox'])
        for width in (320, 390, 1600):
            page = browser.new_page(viewport={'width': width, 'height': 900}, has_touch=True)
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))

            def serve(route):
                path = route.request.url.split('foxworx.test/', 1)[1]
                if not path:
                    route.fulfill(body=html, content_type='text/html')
                elif path.startswith('static/'):
                    asset = ROOT / path
                    route.fulfill(body=asset.read_bytes(), content_type=(
                        'text/css' if path.endswith('.css') else 'text/javascript'))
                else:
                    route.abort()

            page.route('**/*', serve)
            page.goto('https://foxworx.test/')
            page.wait_for_function('window.ready')
            slider = page.locator('#terminal-scroll')
            assert slider.count() == 1, 'Terminal needs a draggable history control'
            assert slider.is_disabled(), 'No history must disable the slider'
            page.evaluate("write(Array.from({length:240},(_,i)=>`line ${i}\\r\\n`).join(''))")
            page.wait_for_function("!document.getElementById('terminal-scroll').disabled")
            page.evaluate("const s=document.getElementById('terminal-scroll');s.value='40';s.dispatchEvent(new Event('input'))")
            page.wait_for_function('term.buffer.active.viewportY===40')
            page.evaluate("write('new output\\r\\n')")
            assert page.evaluate('term.buffer.active.viewportY') == 40, 'New output pulled history to bottom'
            assert 'older' in page.locator('#terminal-scroll-status').inner_text().lower()
            page.locator('#terminal-latest').click()
            page.wait_for_function('term.buffer.active.viewportY===term.buffer.active.baseY')

            # Drag the real slider and use its native keyboard interaction.
            box = slider.bounding_box()
            page.mouse.move(box['x'] + box['width'] - 14, box['y'] + box['height'] / 2)
            page.mouse.down()
            page.mouse.move(box['x'] + box['width'] / 3, box['y'] + box['height'] / 2, steps=12)
            page.mouse.up()
            page.wait_for_function('term.buffer.active.viewportY < term.buffer.active.baseY/2')
            before = page.evaluate('term.buffer.active.viewportY')
            slider.focus()
            page.keyboard.press('ArrowRight')
            page.wait_for_function(f'term.buffer.active.viewportY>{before}')

            # A finger can drag the slider without opening the shell keyboard.
            page.locator('#terminal-latest').click()
            slider.scroll_into_view_if_needed()
            box = slider.bounding_box()
            client = page.context.new_cdp_session(page)
            x, y = box['x'] + box['width'] - 14, box['y'] + box['height'] / 2
            client.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y}]})
            for ratio in (.8, .6, .4, .2):
                client.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': box['x'] + box['width'] * ratio, 'y': y}]})
            client.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
            page.wait_for_function('term.buffer.active.viewportY<term.buffer.active.baseY/2')
            assert not page.evaluate("document.activeElement.classList.contains('xterm-helper-textarea')")

            # Genuine browser touch events: swipe down to older history.
            page.locator('#terminal-latest').click()
            screen = page.locator('.xterm-screen')
            screen.scroll_into_view_if_needed()
            box = screen.bounding_box()
            page_y = page.evaluate('window.scrollY')
            x, y = box['x'] + 80, box['y'] + 50
            client.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y}]})
            for offset in (20, 40, 60, 80, 100):
                client.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x, 'y': y + offset}]})
            client.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
            page.wait_for_function('term.buffer.active.viewportY<term.buffer.active.baseY')
            assert page.evaluate('window.scrollY') == page_y, 'Swipe scrolled the outer page'

            # Fullscreen programs have no normal scrollback; controls restore on exit.
            page.evaluate("write('\\x1b[?1049h')")
            page.wait_for_function("document.getElementById('terminal-scroll').disabled")
            page.evaluate("write('\\x1b[?1049l')")
            page.wait_for_function("!document.getElementById('terminal-scroll').disabled")
            if width < 650:
                assert slider.bounding_box()['height'] >= 44
                assert page.locator('#terminal-latest').bounding_box()['height'] >= 44
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Page overflows on mobile'
            page.evaluate('term.reset()')
            page.wait_for_function("document.getElementById('terminal-scroll').disabled")
            assert not errors, errors
            print(f'PASS: {width}px drag, keyboard, touch, live output, alternate buffer, reset')
            page.close()
        browser.close()


if __name__ == '__main__':
    run()
