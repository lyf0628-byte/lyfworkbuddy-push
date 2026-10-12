import urllib.request
try:
    r = urllib.request.urlopen("http://localhost:8000/")
    html = r.read().decode()
    print("Status:", r.status)
    print("Content-Length:", len(html))
    print("Contains '青禾报销助手':", "青禾报销助手" in html)
    print("Contains '单据报表':", "单据报表" in html)
    print("Contains 'lyf智能体':", "lyf智能体" in html)
    print("\n✅ 首页渲染正常!")
except Exception as e:
    print("❌ 错误:", e)
