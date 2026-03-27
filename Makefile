.PHONY: help install start stop restart clean logs test db-init dev format check build deploy

# 树莓派 SSH 地址，可通过命令行覆盖: make deploy RPI_HOST=ubuntu@192.168.1.100
RPI_HOST ?= ubuntu@raspberrypi.local

# 默认目标
help:
	@echo "VigiDoor 开发辅助命令"
	@echo "====================="
	@echo "make install    - 安装项目依赖"
	@echo "make start      - 启动服务"
	@echo "make stop       - 停止服务"
	@echo "make restart    - 重启服务"
	@echo "make dev        - 开发模式启动"
	@echo "make test       - 运行测试"
	@echo "make db-init    - 初始化数据库"
	@echo "make logs       - 查看实时日志"
	@echo "make clean      - 清理缓存文件"
	@echo "make format     - 格式化代码（需要 black）"
	@echo "make check      - 代码检查（需要 flake8）"
	@echo ""
	@echo "部署相关（建议流程）"
	@echo "make build      - 在本机（树莓派）用 Nuitka 编译为原生二进制"
	@echo "make deploy     - 同步源码到树莓派并重启服务"
	@echo "                  可覆盖目标地址: make deploy RPI_HOST=ubuntu@192.168.1.100"
	@echo "make deploy-build - 同步源码到树莓派并触发远程编译"
	@echo "make deploy-release - 上传本地编译好的 release 包到树莓派"

# 安装依赖
install:
	@echo "安装项目依赖..."
	pip install -r requirements.txt

# 启动服务
start:
	@echo "启动 VigiDoor 服务..."
	bash scripts/start.sh

# 停止服务
stop:
	@echo "停止 VigiDoor 服务..."
	bash scripts/stop.sh

# 重启服务
restart: stop start

# 开发模式启动
dev:
	@echo "开发模式启动..."
	bash scripts/dev_start.sh

# 运行测试
test:
	@echo "运行测试..."
	python -m pytest tests/ -v

# 初始化数据库
db-init:
	@echo "初始化数据库..."
	python db/init_db.py

# 查看实时日志
logs:
	@echo "查看实时日志（Ctrl+C 退出）..."
	tail -f logs/*.log

# 清理缓存和临时文件
clean:
	@echo "清理缓存文件..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.log" -delete 2>/dev/null || true
	rm -rf .pytest_cache
	@echo "清理完成"

# 格式化代码（需要安装 black）
format:
	@echo "格式化代码..."
	black --line-length 100 modules/ core/ db/ mqtt/ utils/ supervisor.py

# 代码检查（需要安装 flake8）
check:
	@echo "代码检查..."
	flake8 modules/ core/ db/ mqtt/ utils/ supervisor.py --max-line-length=100 --ignore=E203,W503

# ── 编译 & 部署 ────────────────────────────────────────────────────────────────

# 在当前机器（树莓派）上用 Nuitka 编译为原生二进制
build:
	@echo "Nuitka 编译（需在树莓派上执行）..."
	bash scripts/build_nuitka.sh

# 同步源码到树莓派（不编译，源码模式运行）
deploy:
	@echo "同步源码到树莓派: $(RPI_HOST)..."
	bash scripts/deploy.sh --host $(RPI_HOST)

# 同步源码到树莓派并触发远程 Nuitka 编译
deploy-build:
	@echo "同步并在树莓派上编译: $(RPI_HOST)..."
	bash scripts/deploy.sh --host $(RPI_HOST) --build

# 上传本地编译好的 release 包（dist/vigidoor-release-*.tar.gz）
deploy-release:
	@echo "上传 release 包到树莓派: $(RPI_HOST)..."
	bash scripts/deploy.sh --host $(RPI_HOST) --release $(shell ls -t dist/vigidoor-release-*.tar.gz 2>/dev/null | head -1)
