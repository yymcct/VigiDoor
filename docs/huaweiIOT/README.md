# huaweiIOT 转发平台

华为云 IoT 推流控制服务，提供 RESTful API 接口，通过华为云 IoTDA 服务向设备发送推流控制命令。

## 功能特性

- ✅ 基于华为云 IoTDA SDK 的设备命令下发
- ✅ 推流开始/停止控制
- ✅ ZLMediaKit Webhook 按需推流（on_stream_not_found / on_stream_none_reader）
- ✅ RESTful API 接口
- ✅ 支持自定义 RTMP 推流地址
- ✅ Docker 容器化部署
- ✅ 健康检查接口
- ✅ 完整的日志记录

## 快速开始

### 本地运行

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 配置环境变量：
```bash
cp .env.example .env
# 编辑 .env 文件，填写华为云配置
```

3. 运行服务：
```bash
make dev
```

### Docker 部署（推荐）

详细的 Docker 部署说明请参考 [README_DOCKER.md](README_DOCKER.md)



