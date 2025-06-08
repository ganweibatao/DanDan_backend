import requests
import json
import time

# 服务器地址
base_url = "http://localhost:8000"

# 测试邮箱
test_email = "751041637@qq.com"

# 发送验证码
send_response = requests.post(
    f"{base_url}/api/v1/accounts/email/send-code/",
    json={"email": test_email}
)
print("发送验证码响应:", send_response.status_code)
print(json.dumps(send_response.json(), indent=2, ensure_ascii=False))

# 等待用户输入收到的验证码
code = input("请输入收到的验证码: ")

# 验证验证码
verify_response = requests.post(
    f"{base_url}/api/v1/accounts/email/verify-code/",
    json={"email": test_email, "code": code}
)
print("验证验证码响应:", verify_response.status_code)
print(json.dumps(verify_response.json(), indent=2, ensure_ascii=False))