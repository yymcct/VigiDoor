import sounddevice as sd

print(sd.query_devices())               # 全部设备
print("\n只看输入设备：")
print(sd.query_devices(kind='input'))