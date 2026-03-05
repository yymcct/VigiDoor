#!/bin/bash

# ========================================
# huaweiIOT 转发平台 Docker 镜像构建与发布脚本
# ========================================

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置区
IMAGE_NAME="huawei-iot-cmd-service"
REGISTRY_URL="${DOCKER_REGISTRY:-yymcct}"  # 可通过环境变量指定镜像仓库地址
VERSION="${VERSION:-v1.0.0}"         # 可通过环境变量指定版本号

# 自动生成版本号（基于日期和 git commit）
if [ "$VERSION" = "latest" ]; then
    GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "nogit")
    DATE_VERSION=$(date +"%Y%m%d-%H%M%S")
    AUTO_VERSION="${DATE_VERSION}-${GIT_COMMIT}"
fi

# ========================================
# 工具函数
# ========================================

print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# ========================================
# 主要功能函数
# ========================================

check_dependencies() {
    print_header "检查依赖"
    
    # 检查 Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker 未安装，请先安装 Docker"
        exit 1
    fi
    print_success "Docker 已安装: $(docker --version)"
    
    # 检查 .env 文件
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            print_warning ".env 文件不存在，将从 .env.example 复制"
            cp .env.example .env
            print_info "请编辑 .env 文件，填写正确的配置信息"
        else
            print_error ".env.example 文件不存在"
            exit 1
        fi
    else
        print_success ".env 文件存在"
    fi
}

build_image() {
    print_header "构建 Docker 镜像"
    
    local build_tag="$IMAGE_NAME:$VERSION"
    
    print_info "镜像标签: $build_tag"
    
    # 构建镜像
    docker build -t "$build_tag" \
        -t "$IMAGE_NAME:latest" \
        -f Dockerfile .
    
    if [ $? -eq 0 ]; then
        print_success "镜像构建成功: $build_tag"
        print_success "附加标签: $IMAGE_NAME:$AUTO_VERSION"
        print_success "附加标签: $IMAGE_NAME:latest"
    else
        print_error "镜像构建失败"
        exit 1
    fi
}

test_image() {
    print_header "测试 Docker 镜像"
    
    local test_container="test-$IMAGE_NAME-$$"
    
    print_info "启动测试容器: $test_container"
    
    # 启动容器（后台运行）
    docker run -d \
        --name "$test_container" \
        -p 5002:5002 \
        --env-file .env \
        "$IMAGE_NAME:latest"
    
    # 等待服务启动
    print_info "等待服务启动..."
    sleep 5
    
    # 检查容器状态
    if docker ps | grep -q "$test_container"; then
        print_success "容器运行正常"
        
        # 检查健康状态（如果支持）
        docker logs "$test_container" | tail -n 20
        
        # 清理测试容器
        print_info "清理测试容器"
        docker stop "$test_container" > /dev/null 2>&1
        docker rm "$test_container" > /dev/null 2>&1
        
        print_success "镜像测试通过"
    else
        print_error "容器启动失败"
        docker logs "$test_container"
        docker rm -f "$test_container" > /dev/null 2>&1
        exit 1
    fi
}

push_image() {
    print_header "推送镜像到仓库"
    
    if [ -z "$REGISTRY_URL" ]; then
        print_warning "未指定镜像仓库地址（DOCKER_REGISTRY），跳过推送"
        return 0
    fi
    
    # 为镜像添加仓库前缀
    local remote_tag="$REGISTRY_URL/$IMAGE_NAME:$VERSION"
    local remote_latest_tag="$REGISTRY_URL/$IMAGE_NAME:latest"
    
    print_info "标记镜像: $remote_tag"
    docker tag "$IMAGE_NAME:$VERSION" "$remote_tag"
    docker tag "$IMAGE_NAME:latest" "$remote_latest_tag"
    
    print_info "推送镜像到仓库..."
    docker push "$remote_tag"
    docker push "$remote_latest_tag"
    
    if [ $? -eq 0 ]; then
        print_success "镜像推送成功"
        print_info "镜像地址: $remote_tag"
        print_info "镜像地址: $remote_latest_tag"
    else
        print_error "镜像推送失败"
        exit 1
    fi
}

save_image() {
    print_header "导出镜像为 tar 文件"
    
    local output_file="${IMAGE_NAME}-${AUTO_VERSION}.tar"
    
    print_info "导出镜像: $IMAGE_NAME:latest -> $output_file"
    docker save -o "$output_file" "$IMAGE_NAME:latest"
    
    if [ $? -eq 0 ]; then
        local file_size=$(du -h "$output_file" | cut -f1)
        print_success "镜像导出成功: $output_file (大小: $file_size)"
        print_info "可使用以下命令加载镜像: docker load -i $output_file"
    else
        print_error "镜像导出失败"
        exit 1
    fi
}

show_info() {
    print_header "构建信息"
    
    echo -e "${BLUE}镜像名称:${NC}    $IMAGE_NAME"
    echo -e "${BLUE}版本标签:${NC}    $VERSION"
    echo -e "${BLUE}自动版本:${NC}    $AUTO_VERSION"
    echo -e "${BLUE}Git Commit:${NC}  $GIT_COMMIT"
    
    if [ -n "$REGISTRY_URL" ]; then
        echo -e "${BLUE}镜像仓库:${NC}    $REGISTRY_URL"
    fi
    
    echo ""
    echo -e "${GREEN}可用的镜像标签:${NC}"
    docker images | grep "$IMAGE_NAME" || echo "  无"
}

show_usage() {
    print_header "使用说明"
    
    cat << EOF
用法: $0 [选项]

选项:
    build       - 仅构建镜像
    test        - 仅测试镜像
    push        - 仅推送镜像（需要先构建）
    save        - 导出镜像为 tar 文件
    all         - 执行完整流程（构建 + 测试 + 推送）
    info        - 显示构建信息
    help        - 显示此帮助信息

环境变量:
    VERSION             - 镜像版本标签（默认: latest）
    DOCKER_REGISTRY     - Docker 镜像仓库地址（例如: registry.example.com）

示例:
    # 构建镜像
    $0 build

    # 构建并测试
    $0 build test

    # 完整流程（构建 + 测试 + 推送）
    VERSION=v1.0.0 DOCKER_REGISTRY=registry.example.com $0 all

    # 导出镜像
    $0 save

    # 推送到私有仓库
    DOCKER_REGISTRY=192.168.1.100:5000 $0 build push
EOF
}

clean() {
    print_header "清理容器和镜像"
    
    # 停止并删除相关容器
    print_info "查找并停止相关容器..."
    local containers=$(docker ps -a --filter "ancestor=$IMAGE_NAME" --format "{{.ID}}" 2>/dev/null)
    if [ -n "$containers" ]; then
        echo "$containers" | xargs docker stop 2>/dev/null || true
        echo "$containers" | xargs docker rm 2>/dev/null || true
        print_success "已停止并删除 $(echo "$containers" | wc -l) 个容器"
    else
        print_info "没有找到相关容器"
    fi
    
    # 删除项目相关镜像
    print_info "删除项目镜像..."
    local images=$(docker images --format "{{.Repository}}:{{.Tag}}" | grep "^$IMAGE_NAME:" 2>/dev/null)
    if [ -n "$images" ]; then
        echo "$images" | xargs docker rmi -f 2>/dev/null || true
        print_success "已删除 $(echo "$images" | wc -l) 个镜像"
    else
        print_info "没有找到项目镜像"
    fi
    
    # 如果指定了仓库地址，也清理远程标签的镜像
    if [ -n "$REGISTRY_URL" ]; then
        print_info "删除远程标签镜像..."
        local remote_images=$(docker images --format "{{.Repository}}:{{.Tag}}" | grep "^$REGISTRY_URL/$IMAGE_NAME:" 2>/dev/null)
        if [ -n "$remote_images" ]; then
            echo "$remote_images" | xargs docker rmi -f 2>/dev/null || true
            print_success "已删除远程标签镜像"
        fi
    fi
    
    # 清理 dangling 镜像
    print_info "清理 dangling 镜像..."
    docker image prune -f
    
    print_success "清理完成"
}

# ========================================
# 主流程
# ========================================

main() {
    cd "$(dirname "$0")"
    
    if [ $# -eq 0 ]; then
        show_usage
        exit 0
    fi
    
    for cmd in "$@"; do
        case "$cmd" in
            build)
                check_dependencies
                build_image
                ;;
            test)
                test_image
                ;;
            push)
                push_image
                ;;
            save)
                save_image
                ;;
            all)
                check_dependencies
                build_image
                test_image
                push_image
                ;;
            info)
                show_info
                ;;
            clean)
                clean
                ;;
            help|--help|-h)
                show_usage
                ;;
            *)
                print_error "未知命令: $cmd"
                show_usage
                exit 1
                ;;
        esac
    done
    
    print_header "完成"
    show_info
}

main "$@"
