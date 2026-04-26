import requests
import json
import time

url = 'http://127.0.0.1:1234/api/v1/models'
load_url = 'http://127.0.0.1:1234/api/v1/models/load'
model = 'qwen2.5-coder-7b-instruct'

for p in [
    {'model': model, 'context_length': 20000},
    {'model': model, 'config': {'context_length': 20000}},
    {'model': model, 'machine_resources': {'context_length': 20000}}
]:
    print('Testing:', p)
    try:
        r = requests.post(load_url, json=p, timeout=10)
        time.sleep(2)
        r_get = requests.get(url)
        data = r_get.json()
        ctx = data['models'][0]['loaded_instances'][0]['config']['context_length']
        print('CTX:', ctx)
        requests.post('http://127.0.0.1:1234/api/v1/models/unload', json={'instance_id': data['models'][0]['loaded_instances'][0]['id']})
        time.sleep(1)
    except Exception as e:
        print('Error:', e)
