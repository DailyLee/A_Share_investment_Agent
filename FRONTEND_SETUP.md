# 前端项目设置指南

本文档说明如何设置和运行前端项目。

## 快速开始

### 1. 安装前端依赖

```bash
cd frontend
npm install
# 或使用 yarn
yarn install
# 或使用 pnpm
pnpm install
```

### 2. 启动后端服务

在项目根目录启动后端服务：

```bash
# 确保已安装 poetry 和项目依赖
poetry install

# 启动后端服务（默认端口 8000）
poetry run python run_with_backend.py
```

### 3. 启动前端开发服务器

在 `frontend` 目录下：

```bash
npm run dev
# 或
yarn dev
# 或
pnpm dev
```

前端将在 `http://localhost:3000` 启动。

### 4. 配置系统参数

1. 打开浏览器访问 `http://localhost:3000`
2. 点击左侧菜单的"系统设置"
3. 填写以下参数：
   - **API Key**: 你的 OPENAI_COMPATIBLE_API_KEY
   - **Base URL**: API 的基础 URL，例如 `https://api.openai.com/v1`
   - **Model**: 模型名称，例如 `gpt-4` 或 `gpt-3.5-turbo`
4. 点击"保存设置"

这些配置会：
- 保存到浏览器的 localStorage（前端持久化）
- 发送到后端并设置到环境变量（运行时生效）

### 5. 使用股票分析功能

1. 在"股票分析"页面输入股票代码（例如：`002848`）
2. 可选：调整新闻数量、初始资金、初始持仓等参数
3. 点击"开始分析"
4. 系统会实时显示分析状态，分析完成后显示结果

### 6. 查看历史报告

1. 点击左侧菜单的"历史报告"
2. 可以看到所有 reports 目录中的历史报告
3. 可以搜索、查看和下载报告

## 技术栈

- **Vue 3**: 前端框架
- **Vite**: 构建工具
- **TypeScript**: 类型支持
- **Tailwind CSS**: 样式框架
- **Element Plus**: UI 组件库
- **Vue Router**: 路由管理
- **Pinia**: 状态管理
- **Axios**: HTTP 客户端

## API 端点

前端通过以下 API 与后端通信：

### 配置相关
- `POST /api/config/set` - 设置系统配置
- `GET /api/config/get` - 获取当前配置

### 分析相关
- `POST /api/analysis/start` - 启动股票分析
- `GET /api/analysis/{run_id}/status` - 获取分析状态
- `GET /api/analysis/{run_id}/result` - 获取分析结果

### 报告相关
- `GET /reports/` - 获取历史报告列表
- `GET /reports/{filename}` - 获取报告内容

## 注意事项

1. **环境变量设置**: 虽然前端可以设置配置，但建议在启动后端服务前通过环境变量或 `.env` 文件设置这些参数，这样更安全且持久。

2. **CORS**: 后端已配置允许所有来源的 CORS 请求，开发环境可以直接使用。生产环境建议限制允许的来源。

3. **分析时间**: 股票分析可能需要较长时间（几分钟），前端会每 2 秒轮询一次状态。

4. **报告格式**: 历史报告文件格式为 `{ticker}_{date}.md`，例如 `600330_20251211.md`。

## 故障排除

### 前端无法连接到后端

- 确保后端服务运行在 `http://localhost:8000`
- 检查浏览器控制台是否有 CORS 错误
- 检查 `vite.config.ts` 中的代理配置

### 分析任务失败

- 检查系统设置中的 API Key、Base URL 和 Model 是否正确
- 检查后端日志查看详细错误信息
- 确保后端有足够的权限访问股票数据源

### 历史报告无法加载

- 确保 `reports` 目录存在于项目根目录
- 检查后端日志查看文件读取错误
- 确保报告文件格式正确（`.md` 扩展名）

## 开发

### 项目结构

```
frontend/
├── src/
│   ├── api/          # API 调用
│   │   ├── client.ts      # Axios 客户端
│   │   ├── analysis.ts    # 分析相关 API
│   │   ├── reports.ts     # 报告相关 API
│   │   └── config.ts      # 配置相关 API
│   ├── router/       # 路由配置
│   ├── stores/       # Pinia 状态管理
│   ├── views/        # 页面组件
│   │   ├── Analysis.vue   # 股票分析页面
│   │   ├── History.vue    # 历史报告页面
│   │   └── Settings.vue    # 系统设置页面
│   ├── App.vue       # 根组件
│   ├── main.ts       # 入口文件
│   └── style.css     # 全局样式
└── ...
```

### 构建生产版本

```bash
npm run build
```

构建产物在 `dist` 目录，可以部署到任何静态文件服务器。
