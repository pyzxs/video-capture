import requests

url = "https://mediakit.cn-beijing.volces.com/api/v1/tasks/amk-tool-erase-video-subtitle-1520752386"
headers = {
    "Authorization": "Bearer AKLTMmEzMzU3Nzc1ZmZjNGNlZWIzOTlhYmE2NzQ1ZDJjODk"
}
response = requests.get(url, headers=headers)
print(response.status_code)
print(response.json())