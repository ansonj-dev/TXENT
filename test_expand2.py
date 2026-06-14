
import urllib.request
import json
req = urllib.request.Request(
    'http://165.245.137.183:8000/node/expand',
    data=json.dumps({'label': 'ESG'}).encode(),
    headers={'Content-Type': 'application/json'}
)
try:
    with urllib.request.urlopen(req) as response:
        print(response.read().decode())
except Exception as e:
    print(e)

