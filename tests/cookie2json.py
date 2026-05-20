import json

# 在这里粘贴你的 Cookie 字符串
cookie_str = "HSID=A3jMBF5g1fbfoGgtD; SSID=AgOxVBRHctvRcz_hf; APISID=example_value"

# 将 Cookie 字符串转换为字典
cookie_dict = {}
for item in cookie_str.split(';'):
    if '=' in item:
        key, value = item.strip().split('=', 1)
        cookie_dict[key] = value

# 转换为格式化的 JSON 字符串并打印
json_output = json.dumps(cookie_dict, indent=2, ensure_ascii=False)
print(json_output)