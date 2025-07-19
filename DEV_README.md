# Development Version Testing

## What's New in Dev Branch

### 🔧 Bug Fixes
- Fixed image ordering issue caused by missing `re` module import
- Improved image sorting logic to handle numeric ordering correctly
- Added retry logic for download failures (3 attempts)
- Better error handling and user feedback

### ✨ New Features

#### 📦 ZIP Archive Support
- Automatically creates and sends ZIP files for large image sets
- Smart Archive Strategy: 
  - ≤5 images: Direct Telegram sending only
  - >5 images: Send images + ZIP archive
- Intelligent File Management: 
  - Automatic file size checking (50MB Telegram limit)
  - Ordered file naming in ZIP (001.jpg, 002.jpg, etc.)
  - Automatic cleanup after sending

#### 🗄️ Storage Management System
- **Automatic Cleanup**: Periodically removes old downloads based on age and storage limits
- **Configurable Retention**: Set custom retention periods (default: 7 days)
- **Storage Limits**: Automatic cleanup when storage exceeds limits (default: 2GB)
- **Background Processing**: Non-blocking cleanup runs every 6 hours

#### 🎯 Smart Cache System
- **Instant Loading**: Cached content loads immediately without re-downloading
- **Access Tracking**: Updates file access times for intelligent cleanup
- **Duplicate Prevention**: Avoids downloading the same content multiple times
- **Cache Status**: Real-time cache hit notifications

#### 🔗 Simple Cache Tracking
- **Download History**: Basic cache tracking using JSON files
- **Storage Insights**: Real-time storage usage and system status
- **Access Tracking**: Updates file access times for intelligent cleanup

#### 🔧 Environment Variables Configuration
All settings are now configurable via environment variables:

**Bot Settings:**
- `BOT_TOKEN`: Telegram bot token (required)

**JM Comic Client:**
- `JM_RETRY_TIMES`: Download retry attempts (default: 3)
- `JM_TIMEOUT`: Request timeout in seconds (default: 30)

**ZIP Archive:**
- `ENABLE_ZIP_ARCHIVE`: Enable ZIP archives (default: true)
- `ZIP_THRESHOLD`: Images threshold for ZIP creation (default: 5)

**Storage Management:**
- `ENABLE_STORAGE_MANAGEMENT`: Enable auto cleanup (default: true)
- `MAX_STORAGE_SIZE_GB`: Storage limit in GB (default: 2.0)
- `KEEP_DAYS`: File retention period (default: 7)
- `CLEANUP_INTERVAL_HOURS`: Cleanup frequency (default: 6)
- `CACHE_DB_PATH`: Cache file path (default: download/cache.json)

**Download Progress:**
- `SHOW_DOWNLOAD_PROGRESS`: Show progress indicators (default: true)
- `PROGRESS_UPDATE_INTERVAL`: Progress update frequency (default: 5)

#### 🤖 Available Commands
- `/start` - Welcome message
- `/cleanup` - Manually trigger storage cleanup
- `/jm <id>` - Download manga by ID

## Docker Deployment

### Using Docker Compose (Recommended)

1. **Setup configuration files:**
```bash
# Create environment variables file
cp .env.example .env
# Edit .env with your bot token and settings

# Create data directory and config
mkdir -p data
cp option.yml.example data/option.yml
# Edit data/option.yml if needed for JM Comic settings
```

2. **Run with docker-compose:**
```bash
docker-compose up -d
```

### Manual Docker Run

```bash
# Pull the dev version
docker pull ghcr.io/deathofbrain/hentai_bot:dev

# Run with environment variables
docker run -d \
  --name hentai_bot_dev \
  -e BOT_TOKEN="your_bot_token_here" \
  -e MAX_STORAGE_SIZE_GB=2.0 \
  -e KEEP_DAYS=7 \
  -v $(pwd)/data/download:/app/download \
  -v $(pwd)/data/option.yml:/app/option.yml \
  ghcr.io/deathofbrain/hentai_bot:dev
```

### Environment Variables Setup

1. **Required Variables**: 
   - `BOT_TOKEN`: Your Telegram bot token (required)

2. **Optional Configuration**: 
   - All other settings have sensible defaults
   - Override any setting using environment variables
   - See complete list in `.env.example`

3. **Volume Mounts**:
   - `/app/download`: Persistent storage for downloads and cache
   - `/app/option.yml`: JM Comic client configuration

### Testing Checklist

#### Basic Functionality
- [ ] Test with small image sets (≤5 images) - should only send images directly
- [ ] Test with large image sets (>5 images) - should send images + ZIP archive
- [ ] Verify image ordering is correct in both direct sending and ZIP archive
- [ ] Test ZIP archive creation and sending
- [ ] Verify file size limits are respected (50MB max)

#### Cache System
- [ ] Test cache hit for previously downloaded content
- [ ] Verify instant loading of cached content
- [ ] Test cache miss for new content

#### Storage Management
- [ ] Test `/cleanup` command - should trigger manual cleanup
- [ ] Verify automatic cleanup after configured intervals
- [ ] Test storage limit enforcement
- [ ] Check cache file persistence

#### Environment Variables
- [ ] Test with different `BOT_TOKEN` values
- [ ] Verify storage settings take effect
- [ ] Test ZIP archive configuration changes
- [ ] Check download progress settings

#### User Experience
- [ ] Test `/start` command
- [ ] Verify progress messages during downloads
- [ ] Check error handling and user-friendly messages
- [ ] Test container restart behavior

### Known Limitations

- ZIP archives are subject to Telegram's 50MB file size limit
- Cache tracking uses JSON files for simplicity
- Background cleanup requires continuous operation
- Storage management is based on file system operations

## Reverting Changes

If you need to revert to the stable version:

```bash
docker pull ghcr.io/deathofbrain/hentai_bot:latest
```