import urllib.request
import json


def test_api():
    base = "http://localhost:8000"

    print("=" * 60)
    print("测试1: 健康检查")
    print("=" * 60)
    resp = urllib.request.urlopen(f"{base}/api/health")
    print(json.loads(resp.read()))

    print("\n" + "=" * 60)
    print("测试2: 单据列表")
    print("=" * 60)
    resp = urllib.request.urlopen(f"{base}/api/documents")
    data = json.loads(resp.read())
    print(f"共 {data['total']} 张单据")

    print("\n" + "=" * 60)
    print("测试3: 查询单据详情 BX202609001")
    print("=" * 60)
    resp = urllib.request.urlopen(f"{base}/api/documents/BX202609001")
    data = json.loads(resp.read())
    print(data["formatted"])

    print("\n" + "=" * 60)
    print("测试4: 财务核对 BX202609005")
    print("=" * 60)
    req = urllib.request.Request(
        f"{base}/api/verify",
        data=json.dumps({"doc_id": "BX202609005"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    print(data["formatted"])

    print("\n" + "=" * 60)
    print("测试5: 智能体对话 - 制度查询")
    print("=" * 60)
    req = urllib.request.Request(
        f"{base}/api/chat",
        data=json.dumps({"message": "差旅费住宿标准是多少？"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    print(data["response"])

    print("\n" + "=" * 60)
    print("测试6: 智能体对话 - 查本人单据状态")
    print("=" * 60)
    req = urllib.request.Request(
        f"{base}/api/chat",
        data=json.dumps({"message": "查询张军的报销单状态"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    print(data["response"])

    print("\n✅ 所有API测试通过!")


if __name__ == "__main__":
    test_api()
