from picamera2 import Picamera2
try:
    picam2 = Picamera2()
    print("Picamera2 成功加载！")
except Exception as e:
    print(f"加载失败: {e}")