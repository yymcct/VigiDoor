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
python main.py
```

### Docker 部署（推荐）

详细的 Docker 部署说明请参考 [README_DOCKER.md](README_DOCKER.md)

快速启动：
```bash
# 1. 配置环境变量
cp .env.example .env
vim .env

# 2. 构建镜像
chmod +x build_and_deploy.sh
./build_and_deploy.sh build

# 3. 启动服务
docker-compose up -d
```

## API 接口

### 1. 健康检查
```bash
GET /health
```

响应示例：
```json
{
  "status": "healthy",
  "service": "stream-control-service",
  "timestamp": 1707812345678
}
```

### 2. 开始推流
```bash
POST /api/v1/stream/start
Content-Type: application/json

{
  "device_id": "VIGIDOOR_xxx_RPI",
  "rtmp_url": "rtmp://server:1935/live/stream",  // 可选
  "params": {}  // 可选
}
```

响应示例：
```json
{
  "success": true,
  "message": "Stream start command sent to device VIGIDOOR_xxx_RPI",
  "device_id": "VIGIDOOR_xxx_RPI",
  "rtmp_url": "rtmp://server:1935/live/stream",
  "msg_id": "f61577db-659b-4179-b187-ce7cd7c8e2cb"
}
```

### 3. 停止推流
```bash
POST /api/v1/stream/stop
Content-Type: application/json

{
  "device_id": "VIGIDOOR_xxx_RPI"
}
```

响应示例：
```json
{
  "success": true,
  "message": "Stream stop command sent to device VIGIDOOR_xxx_RPI",
  "device_id": "VIGIDOOR_xxx_RPI",
  "msg_id": "a82456cd-789e-4567-c123-ab7cd8e9f0ab"
}
```

### 4. 检查配置
```bash
GET /api/v1/config/check
```

---

## ZLMediaKit Webhook 接口（按需推流）

> 实现树莓派按需推流：有人观看时才开始推流，无人观看时自动停止推流。

### ZLMediaKit 配置（zlmediakit.ini）

```ini
on_stream_not_found=http://<本服务地址>:5002/index/hook/on_stream_not_found
on_stream_none_reader=http://<本服务地址>:5002/index/hook/on_stream_none_reader
```

> **约定**: ZLMediaKit 的 `stream` 字段即为设备 ID。
> 例如 stream=`VIGIDOOR_7c3a41081017190d_RPI` 将下发命令至设备 `VIGIDOOR_7c3a41081017190d_RPI`。

### 5. on_stream_not_found

```bash
POST /index/hook/on_stream_not_found
```

触发时机: 某个客户端请求拉流，但 ZLM 中尚无对应的推流。
动作: 向对应的树莓派设备下发 `action=start` 指令，设备收到后开始将视频推至 ZLM。

ZLM 请求体 → 将 `stream` 字段用作 `device_id`，自动构造 RTMP 推流地址:
`rtmp://<ZLM_SERVER>:<ZLM_RTMP_PORT>/<app>/<stream>`

响应： `{ "code": 0, "msg": "success" }`

### 6. on_stream_none_reader

```bash
POST /index/hook/on_stream_none_reader
```

触发时机: 某路流存在但已无任何拉流客户端。
动作: 向对应设备下发 `action=stop` 指令，设备收到后停止推流；同时返回 `close=true` 通知 ZLM 关闭该路流。

响应： `{ "close": true, "code": 0 }`

---

### 4. 检查配置
```bash
GET /api/v1/config/check
```

响应示例：
```json
{
  "success": true,
  "message": "Configuration is valid, IoTDA client initialized",
  "config": {
    "region": "cn-north-4",
    "endpoint": "https://bf0f7e134a.st1.iotda-app.cn-north-4.myhuaweicloud.com",
    "project_id": "ffb9229f0f5942f8a41580da077568a4",
    "ak_configured": true,
    "sk_configured": true
  }
}
```

## 配置说明

### 环境变量

| 变量名 | 说明 | 必填 | 默认值 |
|--------|------|------|--------|
| CLOUD_SDK_AK | 华为云 Access Key | 是 | - |
| CLOUD_SDK_SK | 华为云 Secret Key | 是 | - |
| HUAWEI_PROJECT_ID | 华为云项目 ID | 是 | - |
| HUAWEI_REGION | 华为云区域 | 否 | cn-north-4 |
| IOTDA_ENDPOINT | IoTDA 服务端点 | 是 | - |
| RTMP_URL_TEMPLATE | RTMP 推流地址模板 | 否 | rtmp://zlm-server:1935/live/{device_id} |
| ZLM_SERVER | ZLMediaKit 服务主机名/IP | 否 | zlm-server |
| ZLM_RTMP_PORT | ZLMediaKit RTMP 端口 | 否 | 1935 |
| PORT | 服务端口 | 否 | 5002 |

### 获取华为云配置

1. **Access Key 和 Secret Key**
   - 登录华为云控制台
   - 进入"我的凭证" > "访问密钥"
   - 创建或查看 Access Key

2. **Project ID**
   - 登录华为云控制台
   - 进入"我的凭证" > "API凭证"
   - 查看项目列表中的项目 ID

3. **IoTDA Endpoint**
   - 标准版：`https://iotda.{region}.myhuaweicloud.com`
   - 企业版：`https://{instance_id}.iotda.{region}.myhuaweicloud.com`

## 消息格式

### 发送到设备的消息格式

```json
{
  "msg_id": "f61577db-659b-4179-b187-ce7cd7c8e2cb",
  "timestamp": 1770905346017,
  "device_id": "VIGIDOOR_xxx_RPI",
  "version": "1.0",
  "data": {
    "action": "start",
    "rtmp_url": "rtmp://server:1935/live/stream",
    "params": {}
  }
}
```

### MQTT Topic

命令下发 Topic：`vigidoor/down/{device_id}/command/stream`

## 开发指南

### 目录结构

```
huaweiIOT/
├── main.py                      # 入口文件
├── app/
│   ├── __init__.py              # Flask 工厂函数
│   ├── config.py                # 全局配置项
│   ├── routes/
│   │   ├── health.py            # GET  /health
│   │   ├── stream.py            # POST /api/v1/stream/start|stop
│   │   └── zlm_webhook.py       # POST /index/hook/on_stream_not_found|on_stream_none_reader
│   └── services/
│       └── iotda.py             # 华为云 IoTDA 客户端 & 消息下发
├── requirements.txt             # Python 依赖
├── .env.example                 # 环境变量示例
├── .env                         # 环境变量配置（需自行创建）
├── Dockerfile                   # Docker 镜像构建文件
├── docker-compose.yml           # Docker Compose 配置
├── nginx.conf                   # Nginx 反向代理配置
├── Makefile                     # 快据命令
├── build_and_deploy.sh          # 构建并部署脚本
├── README.md                    # 项目说明
└── README_DOCKER.md             # Docker 部署说明
```

### 添加新功能

1. 在 `stream_control_service.py` 中添加新的路由
2. 实现相应的命令下发逻辑
3. 更新 API 文档

### 测试

```bash
# 健康检查
curl http://localhost:5002/health

# 配置检查
curl http://localhost:5002/api/v1/config/check

# 开始推流
curl -X POST http://localhost:5002/api/v1/stream/start \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "VIGIDOOR_xxx_RPI",
    "rtmp_url": "rtmp://server:1935/live/test"
  }'

# 停止推流
curl -X POST http://localhost:5002/api/v1/stream/stop \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "VIGIDOOR_xxx_RPI"
  }'
```

## 故障排查

### 1. IoTDA 客户端初始化失败

检查环境变量配置：
```bash
docker exec huawei-iot-cmd-service env | grep CLOUD
```

### 2. 设备收不到命令

- 检查设备 ID 是否正确
- 检查 IoTDA 平台上的设备状态
- 查看 Topic 配置是否正确

### 3. 连接超时

- 检查网络连接
- 验证 IoTDA Endpoint 是否正确
- 检查防火墙规则

## 安全建议

1. 不要将 `.env` 文件提交到版本控制系统
2. 定期轮换 Access Key 和 Secret Key
3. 使用 HTTPS 部署服务
4. 限制 API 访问权限（建议添加认证机制）
5. 监控异常日志

## 性能优化

1. 使用连接池
2. 实现消息队列缓冲
3. 添加缓存层
4. 启用 Gunicorn 多进程部署

## 生产部署建议

使用 Gunicorn 作为 WSGI 服务器：

```bash
# 安装 Gunicorn
pip install gunicorn

# 启动服务（4 个 worker 进程）
gunicorn -w 4 -b 0.0.0.0:5002 stream_control_service:app
```

在 Dockerfile 中使用 Gunicorn：
```dockerfile
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5002", "stream_control_service:app"]
```

## 许可证

本项目遵循项目根目录的许可证。

## 联系方式

如有问题或建议，请联系项目维护者。

## 更新日志

### v1.1.0 (2026-03-04)
- ✅ 项目重构为 app/ 包结构
- ✅ 实现 ZLMediaKit Webhook 按需推流
- ✅ 新增 on_stream_not_found / on_stream_none_reader 接口

### v1.0.0 (2026-02-13)
- ✅ 初始版本
- ✅ 实现推流开始/停止控制
- ✅ 添加 Docker 支持
- ✅ 添加健康检查接口
- ✅ 完善文档
