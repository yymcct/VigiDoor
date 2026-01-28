#!/usr/bin/env python3
"""
VigiDoor v2.0 功能测试脚本
用于验证新架构的各个组件
"""

import sys
import time
import numpy as np
from multiprocessing import shared_memory


def test_shared_memory():
    """测试共享内存帧缓冲"""
    print("=" * 60)
    print("测试1: 共享内存帧缓冲")
    print("=" * 60)
    
    try:
        from utils.frame_buffer import SharedFrameBuffer
        
        # 创建写入者
        print("创建共享内存（写入者）...")
        writer = SharedFrameBuffer(
            width=1280,
            height=720,
            name="test_frames",
            create=True
        )
        
        # 写入测试帧
        print("写入测试帧...")
        test_frame = np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8)
        writer.write_frame(test_frame, frame_id=1, timestamp=time.time())
        
        # 创建读取者
        print("创建读取者...")
        reader = SharedFrameBuffer(
            width=1280,
            height=720,
            name="test_frames",
            create=False
        )
        
        # 读取帧
        print("读取帧...")
        result = reader.read_frame(copy=True)
        
        if result:
            frame, frame_id, timestamp = result
            print(f"✅ 读取成功: frame_id={frame_id}, shape={frame.shape}")
            
            # 验证数据一致性
            if np.array_equal(frame, test_frame):
                print("✅ 数据一致性验证通过")
            else:
                print("❌ 数据不一致")
        else:
            print("❌ 读取失败")
        
        # 清理
        reader.close()
        writer.cleanup()
        
        print("✅ 共享内存测试通过\n")
        return True
        
    except Exception as e:
        print(f"❌ 共享内存测试失败: {e}\n")
        return False


def test_camera_process():
    """测试视频采集进程"""
    print("=" * 60)
    print("测试2: 视频采集进程（模拟模式）")
    print("=" * 60)
    
    try:
        import multiprocessing as mp
        import yaml
        
        # 加载配置
        with open('./config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 创建IPC和共享状态
        ipc_queue = mp.Queue()
        shared_state = mp.Manager().dict()
        
        # 启动采集进程
        print("启动采集进程...")
        from modules.camera_process import CameraProcess
        
        process = mp.Process(
            target=lambda: CameraProcess(ipc_queue, shared_state, config).run(),
            name='test_camera'
        )
        process.start()
        
        # 等待启动
        time.sleep(3)
        
        # 检查共享内存
        print("检查共享内存创建...")
        from utils.frame_buffer import SharedFrameBuffer
        
        reader = SharedFrameBuffer(
            width=config['camera']['width'],
            height=config['camera']['height'],
            name=config['camera']['shared_memory_name'],
            create=False
        )
        
        # 读取几帧
        print("读取测试帧...")
        for i in range(5):
            result = reader.read_frame(copy=True)
            if result:
                frame, frame_id, timestamp = result
                print(f"  帧 {i+1}: frame_id={frame_id}, age={time.time()-timestamp:.3f}s")
            time.sleep(0.5)
        
        # 停止进程
        print("停止采集进程...")
        process.terminate()
        process.join(timeout=5)
        
        reader.close()
        
        print("✅ 视频采集测试通过\n")
        return True
        
    except Exception as e:
        print(f"❌ 视频采集测试失败: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_detector_enhancement():
    """测试AI检测增强"""
    print("=" * 60)
    print("测试3: AI检测进程增强（模拟模式）")
    print("=" * 60)
    
    try:
        import multiprocessing as mp
        import yaml
        
        # 加载配置
        with open('./config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 创建IPC和共享状态
        ipc_queue = mp.Queue()
        shared_state = mp.Manager().dict({'global_state': 'safe'})
        
        # 先启动采集进程（提供帧数据）
        print("启动采集进程...")
        from modules.camera_process import CameraProcess
        
        camera_proc = mp.Process(
            target=lambda: CameraProcess(ipc_queue, shared_state, config).run(),
            name='test_camera'
        )
        camera_proc.start()
        time.sleep(2)
        
        # 启动检测进程
        print("启动检测进程...")
        from modules.detector_process import AIDetectorProcess
        
        detector_proc = mp.Process(
            target=lambda: AIDetectorProcess(ipc_queue, shared_state, config).run(),
            name='test_detector'
        )
        detector_proc.start()
        
        # 等待一段时间，检查消息队列
        print("等待检测结果...")
        time.sleep(5)
        
        # 检查消息队列中的检测结果
        result_count = 0
        while not ipc_queue.empty():
            msg = ipc_queue.get_nowait()
            if msg.get('type') == 'detection_result':
                result_count += 1
                print(f"  收到检测结果: {len(msg['data'].get('detections', []))} 个目标")
        
        print(f"共收到 {result_count} 条检测结果消息")
        
        # 停止进程
        print("停止进程...")
        detector_proc.terminate()
        camera_proc.terminate()
        detector_proc.join(timeout=5)
        camera_proc.join(timeout=5)
        
        print("✅ AI检测增强测试通过\n")
        return True
        
    except Exception as e:
        print(f"❌ AI检测测试失败: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_config_validity():
    """测试配置文件完整性"""
    print("=" * 60)
    print("测试4: 配置文件完整性")
    print("=" * 60)
    
    try:
        import yaml
        
        with open('./config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 检查必要配置项
        required_keys = {
            'camera': ['width', 'height', 'target_fps', 'shared_memory_name'],
            'ai_detector': ['detect_interval'],
            'supervisor': {
                'startup_delays': ['camera']
            }
        }
        
        all_ok = True
        
        # 检查camera配置
        if 'camera' not in config:
            print("❌ 缺少 camera 配置")
            all_ok = False
        else:
            for key in required_keys['camera']:
                if key not in config['camera']:
                    print(f"❌ camera.{key} 配置缺失")
                    all_ok = False
                else:
                    print(f"✅ camera.{key} = {config['camera'][key]}")
        
        # 检查ai_detector配置
        if 'detect_interval' not in config.get('ai_detector', {}):
            print("❌ ai_detector.detect_interval 配置缺失")
            all_ok = False
        else:
            print(f"✅ ai_detector.detect_interval = {config['ai_detector']['detect_interval']}")
        
        # 检查supervisor配置
        if 'camera' not in config.get('supervisor', {}).get('startup_delays', {}):
            print("❌ supervisor.startup_delays.camera 配置缺失")
            all_ok = False
        else:
            print(f"✅ supervisor.startup_delays.camera = {config['supervisor']['startup_delays']['camera']}")
        
        if all_ok:
            print("✅ 配置文件完整性测试通过\n")
        else:
            print("❌ 配置文件存在问题\n")
        
        return all_ok
        
    except Exception as e:
        print(f"❌ 配置文件测试失败: {e}\n")
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("  VigiDoor v2.0 架构测试")
    print("=" * 60 + "\n")
    
    results = {
        '共享内存': test_shared_memory(),
        '配置文件': test_config_validity(),
        '视频采集': test_camera_process(),
        'AI检测': test_detector_enhancement(),
    }
    
    print("\n" + "=" * 60)
    print("  测试结果汇总")
    print("=" * 60)
    
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name:12s}: {status}")
    
    print("=" * 60 + "\n")
    
    # 返回退出码
    if all(results.values()):
        print("🎉 所有测试通过！")
        return 0
    else:
        print("⚠️  部分测试失败，请检查日志")
        return 1


if __name__ == '__main__':
    sys.exit(main())
