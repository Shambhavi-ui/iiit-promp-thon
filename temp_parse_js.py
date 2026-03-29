import re
import tempfile
import subprocess
import os

with open('project/index.html', 'r', encoding='utf-8') as f:
    text = f.read()
script = ''.join(re.findall(r'<script>(.*?)</script>', text, flags=re.S))
js = 'new Function(`' + script.replace('`', '\\`') + '`);'
fn = tempfile.NamedTemporaryFile('w', delete=False, suffix='.js')
try:
    fn.write(js)
    fn.close()
    result = subprocess.run(['node', fn.name], capture_output=True, text=True)
    print('node exit', result.returncode)
    print(result.stderr)
finally:
    os.unlink(fn.name)
