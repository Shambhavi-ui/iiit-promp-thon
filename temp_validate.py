import http.client
import pathlib

conn = http.client.HTTPConnection('127.0.0.1', 5000, timeout=10)
conn.request('GET', '/')
r = conn.getresponse()
print('GET / status', r.status)
body = r.read(200)
print('GET / ok', b'<canvas' in body)
conn.close()

boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
file_path = pathlib.Path('project/floorplan.png')
file_data = file_path.read_bytes()
parts = [
    b'--' + boundary.encode(),
    b'Content-Disposition: form-data; name="image"; filename="floorplan.png"',
    b'Content-Type: image/png',
    b'',
    file_data,
    b'--' + boundary.encode() + b'--',
    b''
]
body = b'\r\n'.join(parts)
headers = {
    'Content-Type': 'multipart/form-data; boundary=' + boundary,
    'Content-Length': str(len(body))
}
conn = http.client.HTTPConnection('127.0.0.1', 5000, timeout=30)
conn.request('POST', '/process', body, headers)
r = conn.getresponse()
print('POST /process status', r.status)
response = r.read(500)
print(response[:200])
