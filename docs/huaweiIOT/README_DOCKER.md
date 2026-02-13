# huaweiIOT 转发平台 Docker 部署指南

## 快速开始

### 1. 配置环境变量

复制 `.env.example` 为 `.env` 并填写配置：

```bash
cp .env.example .env
vim .env
```

必需配置项：
- `CLOUD_SDK_AK`: 华为云 Access Key
- `CLOUD_SDK_SK`: 华为云 Secret Key
- `HUAWEI_PROJECT_ID`: 华为云项目 ID
- `IOTDA_ENDPOINT`: IoTDA 服务端点
- `RTMP_URL_TEMPLATE`: 推流地址模板

### 2. 构建镜像

```bash
# 赋予脚本执行权限
chmod +x build_and_deploy.sh

# 构建镜像
./build_and_deploy.sh build
```

### 3. 测试镜像

```bash
# 测试镜像是否正常工作
./build_and_deploy.sh test
```

### 4. 运行容器

#### 方式一：使用 docker run

```bash
docker run -d \
  --name huawei-iot-stream \
  -p 5002:5002 \
  --env-file .env \
  --restart unless-stopped \
  huawei-iot-cmd-service:latest
```

#### 方式二：使用 docker-compose（推荐）

```bash
docker-compose up -d
```

查看日志：
```bash
docker-compose logs -f
```

停止服务：
```bash
docker-compose down
```

## 脚本使用说明

### build_and_deploy.sh 脚本命令

```bash
# 显示帮助信息
./build_and_deploy.sh help

# 构建镜像
./build_and_deploy.sh build

# 测试镜像
./build_and_deploy.sh test

# 推送镜像到仓库
DOCKER_REGISTRY=registry.example.com ./build_and_deploy.sh push

# 导出镜像为 tar 文件
./build_and_deploy.sh save

# 完整流程（构建 + 测试 + 推送）
VERSION=v1.0.0 DOCKER_REGISTRY=registry.example.com ./build_and_deploy.sh all

# 显示构建信息
./build_and_deploy.sh info

# 清理旧镜像
./build_and_deploy.sh clean
```

### 环境变量配置

- `VERSION`: 镜像版本标签（默认: latest）
- `DOCKER_REGISTRY`: Docker 镜像仓库地址

## 高级用法

### 1. 推送到私有镜像仓库

```bash
# 登录私有仓库
docker login registry.example.com

# 构建并推送
DOCKER_REGISTRY=registry.example.com \
VERSION=v1.0.0 \
./build_and_deploy.sh all
```

### 2. 导出镜像离线部署

```bash
# 导出镜像
./build_and_deploy.sh save

# 传输到目标服务器后加载
docker load -i huawei-iot-cmd-service-*.tar

# 运行容器
docker run -d \
  --name huawei-iot-stream \
  -p 5002:5002 \
  --env-file .env \
  huawei-iot-cmd-service:latest
```

### 3. 多架构构建

```bash
# 创建 buildx builder
docker buildx create --name multiarch --use

# 构建多架构镜像
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t registry.example.com/huawei-iot-cmd-service:latest \
  --push \
  -f Dockerfile .
```

## 健康检查

容器内置健康检查，会定期检测服务是否正常运行：

```bash
# 查看容器健康状态
docker ps

# 查看详细健康检查日志
docker inspect huawei-iot-cmd-service | jq '.[0].State.Health'
```

## 日志管理

```bash
# 查看实时日志
docker logs -f huawei-iot-cmd-service

# 查看最近 100 行日志
docker logs --tail 100 huawei-iot-cmd-service

# 使用 docker-compose 查看日志
docker-compose logs -f
```

## 故障排查

### 1. 容器无法启动

```bash
# 查看容器日志
docker logs huawei-iot-cmd-service

# 检查配置文件
docker exec huawei-iot-cmd-service cat /app/.env
```

### 2. 无法连接华为云 IoT

- 检查 AK/SK 是否正确
- 检查网络连接
- 验证 IoTDA 端点地址

### 3. 端口冲突

修改 docker-compose.yml 中的端口映射：
```yaml
ports:
  - "5003:5002"  # 使用其他端口
```

## 资源限制

默认资源限制（可在 docker-compose.yml 中调整）：
- CPU: 最多 1 核，预留 0.5 核
- 内存: 最多 512MB，预留 256MB

## 更新部署

```bash
# 停止旧容器
docker-compose down

# 拉取/构建新镜像
./build_and_deploy.sh build

# 启动新容器
docker-compose up -d
```

## 卸载

```bash
# 停止并删除容器
docker-compose down

# 删除镜像
docker rmi huawei-iot-cmd-service:latest

# 删除数据卷（如有）
docker volume prune
```

## 生产环境建议

1. **使用固定版本标签**：避免使用 `latest`，使用具体版本号
2. **配置反向代理**：使用 Nginx 或 Traefik
3. **启用 HTTPS**：配置 SSL 证书
4. **监控和告警**：集成 Prometheus + Grafana
5. **日志收集**：集成 ELK 或 Loki
6. **备份配置**：定期备份 .env 文件
7. **资源监控**：监控 CPU、内存使用情况

## API 测试

容器启动后，可以测试 API：

```bash
# 健康检查
curl http://localhost:5002/health

# 发送推流命令
curl -X POST http://localhost:5002/api/v1/stream/start \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "your_device_id",
    "rtmp_url": "rtmp://server:1935/live/stream"
  }'
```

## 许可证

请遵守华为云服务条款和相关许可证。
