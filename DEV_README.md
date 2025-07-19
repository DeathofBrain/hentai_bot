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

#### 📊 User Statistics & Analytics
- **Download Tracking**: Comprehensive download history and statistics
- **User Metrics**: Track total downloads, images, and activity
- **Storage Insights**: Real-time storage usage and system status
- **Historical Data**: SQLite database for persistent statistics

#### 🔧 Advanced Configuration
- `ENABLE_STORAGE_MANAGEMENT`: Enable/disable automatic storage management
- `MAX_STORAGE_SIZE_GB`: Maximum storage before cleanup (default: 2GB)
- `KEEP_DAYS`: File retention period (default: 7 days)
- `CLEANUP_INTERVAL_HOURS`: Background cleanup frequency (default: 6 hours)
- `ENABLE_ZIP_ARCHIVE`: Enable/disable ZIP archive functionality
- `ZIP_THRESHOLD`: Threshold for creating ZIP archives (default: 5 images)
- `SHOW_DOWNLOAD_PROGRESS`: Enable/disable download progress indicators

#### 🤖 New Commands
- `/stats` - View personal statistics and system storage status
- `/cleanup` - Manually trigger storage cleanup
- `/start` - Enhanced welcome with user statistics

## Testing with Docker

### Using the Dev Docker Image

```bash
# Pull the dev version
docker pull ghcr.io/deathofbrain/hentai_bot:dev

# Run with your configuration
docker run -d \
  --name hentai_bot_dev \
  -v $(pwd)/option.yml:/app/option.yml \
  -v $(pwd)/download:/app/download \
  ghcr.io/deathofbrain/hentai_bot:dev
```

### Configuration Notes

1. **Storage Management**: 
   - Automatic storage management is enabled by default
   - Default storage limit: 2GB, retention period: 7 days
   - Background cleanup runs every 6 hours
   - You can disable by setting `ENABLE_STORAGE_MANAGEMENT = False`

2. **ZIP Archive Configuration**: 
   - ZIP archive functionality is enabled by default
   - Archives are created for image sets with more than 5 images
   - You can disable by setting `ENABLE_ZIP_ARCHIVE = False`

3. **Cache System**:
   - Automatically detects and uses cached content
   - Updates access times for intelligent retention
   - SQLite database stores download history and statistics

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
- [ ] Test `/stats` command - should show user and system statistics
- [ ] Test `/cleanup` command - should trigger manual cleanup
- [ ] Verify automatic cleanup after configured intervals
- [ ] Test storage limit enforcement

#### User Experience
- [ ] Test enhanced `/start` command with statistics
- [ ] Verify progress messages during downloads
- [ ] Check error handling and user-friendly messages
- [ ] Test database persistence across restarts

### Known Limitations

- ZIP archives are subject to Telegram's 50MB file size limit
- SQLite database requires file system persistence for statistics
- Background cleanup requires continuous operation
- Storage management is based on file system operations

## Reverting Changes

If you need to revert to the stable version:

```bash
docker pull ghcr.io/deathofbrain/hentai_bot:latest
```