# 前端路径配置说明

## 配置概述

前端应用已配置为部署在 `/agent` 路径下。

## 修改的文件

### 1. `frontend/vite.config.ts`
- 添加了 `base: '/agent/'` 配置
- 这确保构建后的静态资源路径都包含 `/agent/` 前缀

### 2. `frontend/src/router/index.ts`
- 更新了 `createWebHistory('/agent/')` 配置
- 这确保 Vue Router 的路由都基于 `/agent/` 路径

### 3. `nginx.conf.example`
- 将前端静态文件服务从根路径 `/` 改为 `/agent` 路径
- 使用 `alias` 指令而不是 `root` 指令（因为路径不是根路径）
- 添加了根路径到 `/agent` 的重定向：`location = / { return 301 /agent/; }`
- 更新了 `try_files` 指令：`try_files $uri $uri/ /agent/index.html;`

## 访问方式

### 开发环境
- 前端开发服务器：`http://localhost:3000/agent/`
- 注意：开发时也需要访问 `/agent/` 路径

### 生产环境
- 前端访问地址：`http://SERVER_HOST:FRONTEND_PORT/agent`
- 根路径自动重定向：访问 `http://SERVER_HOST:FRONTEND_PORT/` 会自动重定向到 `/agent/`

## API 路径

API 路径保持不变，使用绝对路径：
- `/api/*` - 新API端点
- `/reports/*` - 报告API
- `/logs/*` - 日志API
- `/runs/*` - 运行历史API

这些路径通过 nginx 代理到后端，不受前端部署路径影响。

## 注意事项

1. **开发环境**：启动前端开发服务器后，需要访问 `http://localhost:3000/agent/` 而不是 `http://localhost:3000/`

2. **构建产物**：构建后的静态资源会自动包含 `/agent/` 前缀，无需手动修改

3. **路由导航**：Vue Router 的所有路由都会自动基于 `/agent/` 路径，例如：
   - `/agent/` - 分析页面
   - `/agent/history` - 历史报告页面
   - `/agent/settings` - 设置页面

4. **API 调用**：API 客户端使用绝对路径（如 `/api`），不受前端部署路径影响

## 验证配置

部署后，可以通过以下方式验证：

1. 访问根路径应该自动重定向到 `/agent/`
2. 访问 `/agent/` 应该显示前端应用
3. 访问 `/agent/history` 等路由应该正常工作
4. API 调用（如 `/api/config/get`）应该正常工作
