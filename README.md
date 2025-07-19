# 本子机器人 (HentaiBot)

一个基于 Python 的 Telegram 本子下载机器人，支持自动下载、智能缓存和批量压缩包功能。

## 🚀 功能特性

### 📱 核心功能
- **自动下载**: 通过 ID 自动下载指定内容
- **智能发送**: 根据图片数量智能选择发送方式
- **批量处理**: 支持大量图片的分批发送
- **压缩包支持**: 自动为大量图片创建压缩包

### 🗄️ 存储管理
- **智能缓存**: 已下载内容立即加载，无需重复下载
- **自动清理**: 定期清理过期文件，节省存储空间
- **存储限制**: 可配置存储大小限制，自动管理磁盘空间
- **访问追踪**: 智能追踪文件访问时间，优化清理策略

### 📦 压缩包功能
- **智能打包**: 图片超过设定数量时自动创建压缩包
- **有序命名**: ZIP 内文件按顺序重命名 (001.jpg, 002.jpg...)
- **大小检查**: 自动检查文件大小，遵循 Telegram 50MB 限制
- **自动清理**: 发送完成后自动删除临时压缩包

### ⚙️ 配置管理
- **环境变量**: 所有配置通过环境变量管理
- **Docker 支持**: 完整的 Docker 容器化部署
- **持久化存储**: 数据和配置文件持久化映射
- **灵活配置**: 支持自定义各项参数

## 🛠️ 快速开始

### 使用 Docker Compose (推荐)

1. **准备配置文件**
```bash
# 复制环境变量模板
cp .env.example .env
# 编辑 .env 文件，设置你的机器人 token

# 创建数据目录
mkdir -p data
```

2. **启动服务**
```bash
docker-compose up -d
```

### 手动 Docker 运行

```bash
# 拉取镜像
docker pull ghcr.io/deathofbrain/hentai_bot:latest

# 运行容器
docker run -d \
  --name hentai_bot \
  -e BOT_TOKEN="你的机器人token" \
  -v $(pwd)/data/download:/app/download \
  -v $(pwd)/data/option.yml:/app/option.yml \
  ghcr.io/deathofbrain/hentai_bot:latest
```

## 📋 配置说明

### 环境变量配置

所有配置都可以通过环境变量进行设置，详细说明如下：

#### 机器人基础设置
- `BOT_TOKEN`: Telegram 机器人 Token (**必需**)

#### JM 客户端设置
- `JM_RETRY_TIMES`: 下载重试次数 (默认: 2)
- `JM_TIMEOUT`: 请求超时时间，秒 (默认: 15)

#### 压缩包设置
- `ENABLE_ZIP_ARCHIVE`: 启用压缩包功能 (默认: true)
- `ZIP_THRESHOLD`: 创建压缩包的图片数量阈值 (默认: 5)

#### 存储管理设置
- `ENABLE_STORAGE_MANAGEMENT`: 启用存储管理 (默认: true)
- `MAX_STORAGE_SIZE_GB`: 最大存储限制，GB (默认: 2.0)
- `KEEP_DAYS`: 文件保留天数 (默认: 7)
- `CLEANUP_INTERVAL_HOURS`: 清理频率，小时 (默认: 6)
- `CACHE_DB_PATH`: 缓存文件路径 (默认: download/cache.json)

#### 下载进度设置
- `SHOW_DOWNLOAD_PROGRESS`: 显示下载进度 (默认: true)
- `PROGRESS_UPDATE_INTERVAL`: 进度更新间隔，秒 (默认: 5)

### 文件映射

使用 Docker 时需要映射以下文件和目录：

```yaml
volumes:
  # 持久化存储下载和缓存
  - ./data/download:/app/download
  # 环境变量文件映射（可选）
  - ./.env:/app/.env:ro
```

**注意：** JM配置文件已内置在Docker镜像中，无需额外映射。

## 🤖 使用说明

### 可用命令

- `/start` - 显示欢迎信息
- `/jm <ID>` - 下载指定 ID 的内容
- `/cleanup` - 手动触发存储清理

### 使用示例

1. **下载内容**: 发送 `/jm 123456` 下载 ID 为 123456 的内容
2. **缓存命中**: 再次请求相同 ID 会立即从缓存加载
3. **自动压缩**: 图片超过 5 张时会额外提供压缩包下载
4. **存储清理**: 使用 `/cleanup` 手动清理或等待自动清理

## 📁 项目结构

```
hentai_bot/
├── main.py              # 主程序文件
├── requirements.txt     # Python 依赖
├── Dockerfile          # Docker 构建文件
├── docker-compose.yml  # Docker Compose 配置
├── .env.example        # 环境变量模板
├── option.yml          # JM 客户端配置（内置）
└── data/               # 数据目录
    └── download/       # 下载文件存储
```

## ⚡ 智能特性

### 发送策略
- **≤5 张图片**: 直接通过 Telegram 发送
- **>5 张图片**: 发送图片 + 提供压缩包下载

### 缓存机制
- **即时加载**: 已缓存内容无需重新下载
- **智能清理**: 根据访问时间和存储限制自动清理
- **重复检测**: 避免重复下载相同内容

### 错误处理
- **自动重试**: 下载失败时自动重试最多 3 次
- **用户友好**: 提供清晰的错误信息和处理进度
- **容错设计**: 处理各种异常情况，确保服务稳定

## 🔧 故障排除

### 常见问题

1. **机器人无响应**
   - 检查 `BOT_TOKEN` 是否正确设置
   - 确认容器正常运行: `docker logs hentai_bot`

2. **下载失败**
   - 检查网络连接
   - 查看 `option.yml` 配置是否正确
   - 检查存储空间是否足够

3. **压缩包过大**
   - Telegram 限制文件大小为 50MB
   - 可以调整 `ZIP_THRESHOLD` 减少压缩包中的图片数量

4. **存储空间问题**
   - 调整 `MAX_STORAGE_SIZE_GB` 设置
   - 手动执行 `/cleanup` 命令
   - 检查 `KEEP_DAYS` 设置

### 日志查看

```bash
# 查看容器日志
docker logs -f hentai_bot

# 查看最近日志
docker logs --tail 100 hentai_bot
```

## 📊 性能优化

- **后台清理**: 存储清理在后台运行，不影响用户体验
- **智能缓存**: 减少重复下载，节省带宽和时间
- **批量处理**: 高效处理大量图片
- **资源管理**: 自动管理存储空间，防止磁盘溢出

## 🔒 安全说明

- 机器人不存储用户个人信息
- 所有配置通过环境变量管理，避免敏感信息泄露
- 下载内容仅在本地存储，支持自动清理

## 📈 开发版本

如需测试最新功能，可以使用开发版本：

```bash
docker pull ghcr.io/deathofbrain/hentai_bot:dev
```

查看 `DEV_README.md` 了解开发版本的详细信息和测试说明。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request 来改进这个项目。

## 📄 许可证

本项目采用开源许可证，详情请查看项目根目录的 LICENSE 文件。