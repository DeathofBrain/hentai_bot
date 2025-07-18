# Development Version Testing

## What's New in Dev Branch

### 🔧 Bug Fixes
- Fixed image ordering issue caused by missing `re` module import
- Improved image sorting logic to handle numeric ordering correctly

### ✨ New Features
- **Telegraph Upload Support**: Automatically uploads large image sets (>10 images) to Telegraph for better handling
- **Smart Sending Strategy**: 
  - ≤10 images: Direct Telegram sending (traditional method)
  - >10 images: Upload to Telegraph and return a single link
- **Fallback Mechanism**: If Telegraph upload fails, automatically falls back to traditional method
- **Configuration Options**: 
  - `TELEGRAPH_ENABLED`: Enable/disable Telegraph functionality
  - `TELEGRAPH_THRESHOLD`: Set the threshold for using Telegraph (default: 10 images)

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

1. **Telegraph Configuration**: 
   - Telegraph functionality is enabled by default
   - If Telegraph service is unavailable, the bot will automatically fall back to traditional sending
   - You can disable Telegraph by setting `TELEGRAPH_ENABLED = False` in main.py

2. **Image Threshold**:
   - Default threshold is 10 images
   - Adjust `TELEGRAPH_THRESHOLD` in main.py to change when Telegraph is used

### Testing Checklist

- [ ] Test with small image sets (≤10 images) - should use direct Telegram sending
- [ ] Test with large image sets (>10 images) - should attempt Telegraph upload
- [ ] Verify image ordering is correct
- [ ] Test fallback mechanism when Telegraph is unavailable
- [ ] Verify bot responds appropriately to invalid inputs

### Known Limitations

- Telegraph upload API has been restricted due to abuse, so it may not work in all cases
- The bot includes robust fallback mechanisms to ensure functionality even when Telegraph is unavailable

## Reverting Changes

If you need to revert to the stable version:

```bash
docker pull ghcr.io/deathofbrain/hentai_bot:latest
```