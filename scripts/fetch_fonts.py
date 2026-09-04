"""Self-host two public Google Fonts so the preview needs no remote requests."""
import re
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

root = Path(__file__).resolve().parents[1]
target = root / 'public' / 'assets'
target.mkdir(exist_ok=True)
ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'

def get(url):
    with urlopen(Request(url, headers={'User-Agent': ua}), timeout=25) as response:
        return response.read()

copy = '\n'.join((root / 'public' / name).read_text(encoding='utf-8') for name in ('app.js', 'workspace.js', 'logistics-model.js', 'pacific-clock.js'))
chinese = ''.join(sorted(set(re.findall(r'[\u3400-\u9fff]', copy))))
for family, filename, text in [('Manrope:wght@200..800', 'manrope.woff2', None), ('Noto Sans SC:wght@100..900', 'noto-sans-sc.woff2', chinese)]:
    params = {'family': family, 'display': 'swap'}
    if text:
        params['text'] = text
    css = get('https://fonts.googleapis.com/css2?' + urlencode(params)).decode('utf-8')
    urls = re.findall(r'url\((https://[^)]+)\)', css)
    if not urls:
        raise RuntimeError('No font asset returned')
    font = get(urls[-1])
    if font[:4] != b'wOF2':
        raise RuntimeError('Expected WOFF2 font')
    (target / filename).write_bytes(font)
    print(f'{filename}: {len(font)} bytes')

for family in ('manrope', 'notosanssc'):
    license_text = get(f'https://raw.githubusercontent.com/google/fonts/main/ofl/{family}/OFL.txt')
    if b'SIL OPEN FONT LICENSE' not in license_text:
        raise RuntimeError('Expected the official font license')
    (target / f'{family}-OFL.txt').write_text('\n'.join(line.rstrip() for line in license_text.decode('utf-8').splitlines()) + '\n', encoding='utf-8')
