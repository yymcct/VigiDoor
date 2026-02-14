.PHONY: help install start stop restart clean logs test db-init dev format check

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
