import base64
import hashlib
import io
import json
from pathlib import Path
import tarfile
from urllib.request import urlopen

root = Path(__file__).resolve().parents[1] / 'public/vendor'
with urlopen('https://registry.npmjs.org/countup.js/2.9.0', timeout=30) as response:
    metadata = json.load(response)
assert metadata['name'] == 'countup.js' and metadata['version'] == '2.9.0'
with urlopen(metadata['dist']['tarball'], timeout=30) as response:
    package = response.read()
assert 'sha512-' + base64.b64encode(hashlib.sha512(package).digest()).decode() == metadata['dist']['integrity']
with tarfile.open(fileobj=io.BytesIO(package), mode='r:gz') as archive:
    script = archive.extractfile('package/dist/countUp.umd.js').read()
    license_name = next(name for name in archive.getnames() if name.lower() in ('package/license', 'package/license.txt', 'package/license.md'))
    license_text = archive.extractfile(license_name).read()
assert b'CountUp' in script and b'MIT' in license_text
root.mkdir(exist_ok=True)
(root / 'countUp.umd.js').write_bytes(script)
(root / 'countUp-LICENSE.txt').write_text('\n'.join(line.rstrip() for line in license_text.decode().splitlines()) + '\n', encoding='utf-8')
print(json.dumps({'package':metadata['name'], 'version':metadata['version'], 'bytes':len(script), 'integrityVerified':True}))
