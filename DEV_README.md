# Development Version Testing

## What's New in Dev Branch

### 🔧 Bug Fixes
- Fixed image ordering issue caused by missing `re` module import
- Improved image sorting logic to handle numeric ordering correctly
- Added retry logic for download failures (3 attempts)
- Better error handling and user feedback

### ✨ New Features
- **ZIP Archive Support**: Automatically creates and sends ZIP files for large image sets
- **Smart Archive Strategy**: 
  - ≤5 images: Direct Telegram sending only
  - >5 images: Send images + ZIP archive
- **Intelligent File Management**: 
  - Automatic file size checking (50MB Telegram limit)
  - Ordered file naming in ZIP (001.jpg, 002.jpg, etc.)
  - Automatic cleanup after sending
- **Configuration Options**: 
  - `ENABLE_ZIP_ARCHIVE`: Enable/disable ZIP archive functionality
  - `ZIP_THRESHOLD`: Set the threshold for creating ZIP archives (default: 5 images)

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

1. **ZIP Archive Configuration**: 
   - ZIP archive functionality is enabled by default
   - Archives are created for image sets with more than 5 images
   - You can disable archives by setting `ENABLE_ZIP_ARCHIVE = False` in main.py

2. **Image Threshold**:
   - Default threshold is 5 images
   - Adjust `ZIP_THRESHOLD` in main.py to change when ZIP archives are created

### Testing Checklist

- [ ] Test with small image sets (≤5 images) - should only send images directly
- [ ] Test with large image sets (>5 images) - should send images + ZIP archive
- [ ] Verify image ordering is correct in both direct sending and ZIP archive
- [ ] Test ZIP archive creation and sending
- [ ] Verify file size limits are respected (50MB max)
- [ ] Check automatic cleanup of temporary ZIP files

### Known Limitations

- ZIP archives are subject to Telegram's 50MB file size limit
- Large image sets may result in large ZIP files that exceed the limit
- The bot automatically handles file size checking and cleanup

## Reverting Changes

If you need to revert to the stable version:

```bash
docker pull ghcr.io/deathofbrain/hentai_bot:latest
```