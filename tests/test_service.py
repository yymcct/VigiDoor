#!/usr/bin/env python3
"""
推流控制服务测试脚本
"""

import requests
import json
import time

# 服务地址
BASE_URL = "http://localhost:5002"

def test_health():
    """测试健康检查接口"""
    print("\n========== 测试健康检查接口 ==========")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        return response.status_code == 200
    except Exception as e:
        print(f"错误: {str(e)}")
        return False


def test_start_stream(device_id="RPI_001", rtmp_url=None):
    """测试开始推流接口"""
    print(f"\n========== 测试开始推流接口 (设备: {device_id}) ==========")
    
    payload = {
        "device_id": device_id
    }
    
    if rtmp_url:
        payload["rtmp_url"] = rtmp_url
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/stream/start",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        return response.status_code == 200
    except Exception as e:
        print(f"错误: {str(e)}")
        return False


def test_stop_stream(device_id="RPI_001"):
    """测试停止推流接口"""
    print(f"\n========== 测试停止推流接口 (设备: {device_id}) ==========")
    
    payload = {
        "device_id": device_id
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/stream/stop",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        return response.status_code == 200
    except Exception as e:
        print(f"错误: {str(e)}")
        return False


def test_refresh_token():
    """测试刷新 Token 接口"""
    print("\n========== 测试刷新 Token 接口 ==========")
    try:
        response = requests.post(f"{BASE_URL}/api/v1/token/refresh")
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        return response.status_code == 200
    except Exception as e:
        print(f"错误: {str(e)}")
        return False


def test_invalid_request():
    """测试无效请求"""
    print("\n========== 测试无效请求（缺少 device_id）==========")
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/stream/start",
            json={},
            headers={"Content-Type": "application/json"}
        )
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        return response.status_code == 400
    except Exception as e:
        print(f"错误: {str(e)}")
        return False


def main():
    """主测试函数"""
    print("=" * 60)
    print("华为云 IoT 推流控制服务测试")
    print("=" * 60)
    
    results = []
    
    # 1. 健康检查
    results.append(("健康检查", test_health()))
    

    time.sleep(1)
    
    # 3. 开始推流测试
    results.append(("开始推流", test_start_stream(
        device_id="VIGIDOOR_7c3a41081017190d_RPI",
        rtmp_url="rtsp://192.168.38.166:8554/live/VIGIDOOR_7c3a41081017190d_RPI"
    )))
    
    time.sleep(10)
    
    # 4. 停止推流测试
    results.append(("停止推流", test_stop_stream(device_id="VIGIDOOR_7c3a41081017190d_RPI")))
    
    time.sleep(1)
    
    # 5. 无效请求测试
    results.append(("无效请求处理", test_invalid_request()))
    
    # 打印测试结果汇总
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{test_name}: {status}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\n总计: {passed}/{total} 个测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！")
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，请检查日志")


if __name__ == "__main__":
    main()
