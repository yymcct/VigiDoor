.PHONY: help build test run stop clean push save info

# 默认目标
.DEFAULT_GOAL := help

# 镜像配置
IMAGE_NAME := huawei-iot-cmd-service
VERSION := latest
REGISTRY := $(DOCKER_REGISTRY)

help: ## 显示帮助信息
	@echo "huaweiIOT 转发平台 - 可用命令:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "环境变量:"
	@echo "  VERSION          - 镜像版本 (默认: latest)"
	@echo "  DOCKER_REGISTRY  - 镜像仓库地址"
	@echo ""

setup: ## 初始化环境（复制 .env.example 到 .env）
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "✓ 已创建 .env 文件，请编辑填写配置"; \
	else \
		echo "✓ .env 文件已存在"; \
	fi

build: setup ## 构建 Docker 镜像
	@./build_and_deploy.sh build

test: ## 测试 Docker 镜像
	@./build_and_deploy.sh test

run: ## 使用 docker-compose 启动服务
	@docker-compose up -d
	@echo "✓ 服务已启动"
	@echo "  查看日志: make logs"
	@echo "  停止服务: make stop"

stop: ## 停止服务
	@docker-compose down
	@echo "✓ 服务已停止"

restart: stop run ## 重启服务

logs: ## 查看服务日志
	@docker-compose logs -f

status: ## 查看服务状态
	@docker-compose ps

push: ## 推送镜像到仓库
	@./build_and_deploy.sh push

save: ## 导出镜像为 tar 文件
	@./build_and_deploy.sh save

info: ## 显示构建信息
	@./build_and_deploy.sh info

clean: ## 清理旧镜像和容器
	@docker-compose down -v || true
	@./build_and_deploy.sh clean || true
	@echo "✓ 清理完成"

all: build test ## 构建并测试镜像

deploy: all run ## 完整部署流程（构建 + 测试 + 启动）

shell: ## 进入容器 shell
	@if docker ps --format '{{.Names}}' | grep -q '^huawei-iot-cmd-service$$'; then \
		docker exec -it huawei-iot-cmd-service /bin/bash; \
	else \
		echo "错误: 容器未运行，请先执行 'make run' 启动服务"; \
		exit 1; \
	fi

health: ## 检查服务健康状态
	@curl -s http://localhost:5002/health | python3 -m json.tool || echo "错误: 无法连接到服务，请确认服务是否运行 (make status)"

config-check: ## 检查配置是否正确
	@curl -s http://localhost:5002/api/v1/config/check | python3 -m json.tool || echo "错误: 无法连接到服务，请确认服务是否运行 (make status)"

dev: ## 开发模式运行（本地 Python）
	@python stream_control_service.py

install: ## 安装 Python 依赖
	@pip install -r requirements.txt
	@echo "✓ 依赖安装完成"

lint: ## 代码格式检查（需要安装 flake8）
	@flake8 stream_control_service.py config.py || echo "提示: 安装 flake8 进行代码检查: pip install flake8"

backup: ## 备份配置文件
	@mkdir -p backups
	@cp .env backups/.env.backup.$(shell date +%Y%m%d-%H%M%S)
	@echo "✓ 配置已备份到 backups/"

# 快捷命令
up: run ## 启动服务（run 的别名）
down: stop ## 停止服务（stop 的别名）
ps: status ## 查看状态（status 的别名）
