#!/bin/bash

# 设置颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 启动RAG智能问答系统...${NC}"

# 第一步：导入环境变量
echo -e "${YELLOW}📋 第1步：导入环境变量...${NC}"
export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/credentials/cy-aispeci-demo-da47ddabfaf6.json"
export PROJECT_ROOT="$(pwd)"

# 验证环境变量
if [ ! -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    echo -e "${RED}❌ 错误：GCP认证文件不存在: $GOOGLE_APPLICATION_CREDENTIALS${NC}"
    echo -e "${YELLOW}提示：请确保凭据文件位于 credentials/ 目录下${NC}"
    exit 1
fi

echo -e "${GREEN}✅ 环境变量设置完成${NC}"
echo "   - GCP认证文件: $GOOGLE_APPLICATION_CREDENTIALS"
echo "   - 项目根目录: $PROJECT_ROOT"

# 第二步：杀死老进程
echo -e "${YELLOW}📋 第2步：清理旧进程...${NC}"

# 杀死可能占用端口的进程
echo "🔍 查找占用端口8080和3000的进程..."
BACKEND_PORTS=$(lsof -ti:8080 2>/dev/null || true)
FRONTEND_PORTS=$(lsof -ti:3000 2>/dev/null || true)

if [ ! -z "$BACKEND_PORTS" ]; then
    echo "🔪 杀死占用端口8080的进程: $BACKEND_PORTS"
    kill -9 $BACKEND_PORTS 2>/dev/null || true
fi

if [ ! -z "$FRONTEND_PORTS" ]; then
    echo "🔪 杀死占用端口3000的进程: $FRONTEND_PORTS"
    kill -9 $FRONTEND_PORTS 2>/dev/null || true
fi

# 清理PID文件
mkdir -p "$PROJECT_ROOT/logs"
mkdir -p "$PROJECT_ROOT/pids"

if [ -f "$PROJECT_ROOT/pids/backend.pid" ]; then
    OLD_PID=$(cat "$PROJECT_ROOT/pids/backend.pid")
    kill -9 $OLD_PID 2>/dev/null || true
    rm -f "$PROJECT_ROOT/pids/backend.pid"
    echo "🗑️ 清理旧的后端PID文件: $OLD_PID"
fi

if [ -f "$PROJECT_ROOT/pids/frontend.pid" ]; then
    OLD_PID=$(cat "$PROJECT_ROOT/pids/frontend.pid")
    kill -9 $OLD_PID 2>/dev/null || true
    rm -f "$PROJECT_ROOT/pids/frontend.pid"
    echo "🗑️ 清理旧的前端PID文件: $OLD_PID"
fi

# 额外清理：杀死所有相关的Python和Node进程
echo "🧹 清理所有相关进程..."
pkill -f "api_server.py" 2>/dev/null || true
pkill -f "npm start" 2>/dev/null || true
pkill -f "react-scripts start" 2>/dev/null || true

sleep 2
echo -e "${GREEN}✅ 旧进程清理完成${NC}"

# 第三步：同时启动前后端服务
echo -e "${YELLOW}📋 第3步：启动前后端服务...${NC}"

# 创建日志文件
: > "$PROJECT_ROOT/logs/backend.log"
: > "$PROJECT_ROOT/logs/frontend.log"

# 启动后端服务器
echo "🔧 启动后端API服务器..."
cd "$PROJECT_ROOT"
nohup env GOOGLE_APPLICATION_CREDENTIALS="$GOOGLE_APPLICATION_CREDENTIALS" PROJECT_ROOT="$PROJECT_ROOT" python api_server.py > logs/backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > pids/backend.pid

# 等待后端启动
echo "⏳ 等待后端服务启动..."
sleep 5

# 检查后端是否启动成功
BACKEND_CHECK=0
for i in {1..20}; do
    if curl -s http://localhost:8080/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ 后端API服务器启动成功 (PID: $BACKEND_PID)${NC}"
        BACKEND_CHECK=1
        break
    fi
    echo "⏳ 等待后端启动... ($i/20)"
    sleep 2
done

if [ $BACKEND_CHECK -eq 0 ]; then
    echo -e "${RED}❌ 后端服务器启动失败，查看日志：${NC}"
    tail -20 logs/backend.log
    exit 1
fi

# 启动前端服务器
echo "🎨 启动前端开发服务器..."
cd "$PROJECT_ROOT/frontend"

# 检查是否已安装依赖
if [ ! -d "node_modules" ]; then
    echo "📦 安装前端依赖..."
    npm install
fi

# 启动前端
export GENERATE_SOURCEMAP=false
nohup npm start > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > ../pids/frontend.pid

# 等待前端启动
echo "⏳ 等待前端服务启动..."
sleep 3
FRONTEND_CHECK=0
for i in {1..10}; do
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        echo -e "${GREEN}✅ 前端开发服务器启动成功 (PID: $FRONTEND_PID)${NC}"
        FRONTEND_CHECK=1
        break
    fi
    echo "⏳ 等待前端启动... ($i/10)"
    sleep 2
done

if [ $FRONTEND_CHECK -eq 0 ]; then
    echo -e "${RED}❌ 前端服务器启动失败，查看日志：${NC}"
    tail -20 ../logs/frontend.log
    echo -e "${YELLOW}⚠️  继续运行，前端可能需要更长时间启动${NC}"
fi

echo -e "${GREEN}✅ 系统启动完成！${NC}"
echo -e "${GREEN}📱 前端地址: http://localhost:3000${NC}"
echo -e "${GREEN}🔌 后端API: http://localhost:8080${NC}"
echo ""
echo -e "${BLUE}📊 实时日志显示：${NC}"
echo -e "${YELLOW}按 Ctrl+C 停止系统${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 定义清理函数
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 正在停止系统...${NC}"
    
    # 杀死子进程
    if [ ! -z "$BACKEND_PID" ]; then
        kill -9 $BACKEND_PID 2>/dev/null || true
        echo "🔪 已停止后端服务 (PID: $BACKEND_PID)"
    fi
    
    if [ ! -z "$FRONTEND_PID" ]; then
        kill -9 $FRONTEND_PID 2>/dev/null || true
        echo "🔪 已停止前端服务 (PID: $FRONTEND_PID)"
    fi
    
    # 清理PID文件
    rm -f "$PROJECT_ROOT/pids/backend.pid"
    rm -f "$PROJECT_ROOT/pids/frontend.pid"
    
    echo -e "${GREEN}✅ 系统已完全停止${NC}"
    exit 0
}

# 设置信号处理
trap cleanup INT TERM

# 实时显示日志
cd "$PROJECT_ROOT"
tail -f logs/backend.log logs/frontend.log 