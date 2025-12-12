# A股投资分析系统 - 前端

这是一个基于 Vue 3 + Vite + TypeScript + Tailwind CSS + Element Plus 的前端应用。

## 技术栈

- **Vue 3**: 渐进式 JavaScript 框架
- **Vite**: 下一代前端构建工具
- **TypeScript**: JavaScript 的超集，提供类型支持
- **Tailwind CSS**: 实用优先的 CSS 框架
- **Element Plus**: Vue 3 组件库
- **Vue Router**: Vue.js 官方路由管理器
- **Pinia**: Vue 的状态管理库
- **Axios**: HTTP 客户端
- **Marked**: Markdown 解析器

## 功能特性

1. **系统设置**: 配置 OPENAI_COMPATIBLE_API_KEY、OPENAI_COMPATIBLE_BASE_URL 和 OPENAI_COMPATIBLE_MODEL
2. **股票分析**: 输入股票代码，启动分析任务，实时查看分析状态和结果
3. **历史报告**: 查看 reports 目录中的所有历史分析报告

## 安装和运行

### 前置要求

- Node.js >= 16.0.0
- npm 或 yarn 或 pnpm

### 安装依赖

```bash
cd frontend
npm install
# 或
yarn install
# 或
pnpm install
```

### 开发模式

```bash
npm run dev
# 或
yarn dev
# 或
pnpm dev
```

应用将在 `http://localhost:3000` 启动。

### 构建生产版本

```bash
npm run build
# 或
yarn build
# 或
pnpm build
```

构建产物将输出到 `dist` 目录。

### 预览生产构建

```bash
npm run preview
# 或
yarn preview
# 或
pnpm preview
```

## 后端服务

前端需要后端服务运行在 `http://localhost:8000`。请确保后端服务已启动：

```bash
# 在项目根目录
poetry run python run_with_backend.py
```

## 项目结构

```
frontend/
├── src/
│   ├── api/          # API 调用相关
│   ├── router/       # 路由配置
│   ├── stores/       # Pinia 状态管理
│   ├── views/        # 页面组件
│   ├── App.vue       # 根组件
│   ├── main.ts       # 入口文件
│   └── style.css     # 全局样式
├── index.html        # HTML 模板
├── package.json      # 项目配置和依赖
├── tsconfig.json     # TypeScript 配置
├── vite.config.ts    # Vite 配置
└── tailwind.config.js # Tailwind CSS 配置
```

## API 端点

前端通过以下 API 端点与后端通信：

- `POST /api/analysis/start` - 启动股票分析
- `GET /api/analysis/{run_id}/status` - 获取分析状态
- `GET /api/analysis/{run_id}/result` - 获取分析结果
- `GET /reports/` - 获取历史报告列表
- `GET /reports/{filename}` - 获取报告内容

## 注意事项

1. 系统设置中的 API Key、Base URL 和 Model 配置会保存到浏览器的 localStorage 中，但实际使用时，后端需要从环境变量读取这些配置。
2. 分析任务可能需要较长时间，前端会每 2 秒轮询一次状态。
3. 历史报告从后端的 `reports` 目录读取，文件名格式为 `{ticker}_{date}.md`。
