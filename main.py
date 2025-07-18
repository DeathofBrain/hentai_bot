import glob
import logging
import re
import requests
import json
import os
import time
import jmcomic
from jmcomic import *
from telegram import Update, InputMediaPhoto
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, filters, MessageHandler

from options import *

# JM客户端创建
option = jmcomic.create_option_by_file('./option.yml')
# 添加重试和超时配置
option.client.retry_times = 3
option.client.timeout = 30
client = option.new_jm_client()

# Telegraph功能开关 (当Telegraph服务不可用时可以关闭)
TELEGRAPH_ENABLED = True
TELEGRAPH_THRESHOLD = 10  # 超过多少张图片时使用Telegraph

# 测试Telegraph是否可用
def test_telegraph_availability():
    """测试Telegraph服务是否可用"""
    try:
        response = requests.get('https://telegra.ph', timeout=5)
        return response.status_code == 200
    except:
        return False

# 在启动时检查Telegraph可用性
if TELEGRAPH_ENABLED:
    if not test_telegraph_availability():
        print("⚠️  Telegraph服务不可用，已自动禁用")
        TELEGRAPH_ENABLED = False

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text="欢迎使用DouJin机器人！为您自动获取指定本子哟，祝起飞愉快~⭐")


async def bind_pica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text="请输入哔咔账号与密码 本bot承诺不会存储任何信息")


def upload_to_telegraph(image_path):
    """上传图片到Telegraph并返回URL"""
    try:
        # 检测文件类型
        file_ext = image_path.lower().split('.')[-1]
        content_type = 'image/jpeg'
        if file_ext in ['png']:
            content_type = 'image/png'
        elif file_ext in ['gif']:
            content_type = 'image/gif'
        
        with open(image_path, 'rb') as f:
            url = 'https://telegra.ph/upload'
            files = {'file': (f'image.{file_ext}', f, content_type)}
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.post(url, files=files, headers=headers, timeout=30)
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    if isinstance(result, list) and len(result) > 0 and 'src' in result[0]:
                        return f'https://telegra.ph{result[0]["src"]}'
                    else:
                        print(f"Telegraph返回格式错误: {result}")
                        return None
                except json.JSONDecodeError:
                    print(f"Telegraph返回非JSON格式: {response.text}")
                    return None
            else:
                print(f"Telegraph上传失败: HTTP {response.status_code}, {response.text}")
                return None
    except Exception as e:
        print(f"上传到Telegraph失败: {e}")
        return None


def create_telegraph_page(title, image_urls):
    """创建Telegraph页面包含所有图片"""
    # 由于Telegraph页面创建需要access token，我们改用简单的方式
    # 直接返回第一张图片的URL作为代表，并在消息中列出所有图片
    if image_urls:
        message = f"📸 {title}\n\n包含 {len(image_urls)} 张图片:\n"
        # 显示前5个URL
        for i, url in enumerate(image_urls[:5]):
            message += f"{i+1}. {url}\n"
        if len(image_urls) > 5:
            message += f"... 还有 {len(image_urls)-5} 张图片"
        return message
    return None

def create_image_summary(title, image_paths):
    """创建图片摘要信息，不依赖Telegraph"""
    if image_paths:
        message = f"📸 {title}\n\n"
        message += f"共 {len(image_paths)} 张图片已准备就绪\n"
        message += f"由于图片数量较多，将分批发送（每批最多10张）\n"
        message += f"预计发送 {(len(image_paths) + 9) // 10} 批次"
        return message
    return None


async def send_images_traditional(context, chat_id, image_paths):
    """传统方式发送图片，10张打包"""
    batch_size = 10
    for i in range(0, len(image_paths), batch_size):
        media_group = []
        
        for path in image_paths[i:i + batch_size]:
            with open(path, "rb") as f:
                media_group.append(InputMediaPhoto(media=f.read()))
        
        if media_group:
            await context.bot.send_media_group(chat_id=chat_id, media=media_group)


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text=update.message.text)


async def jm_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 获取指令后参数
    args = context.args
    # 如果是jm_id
    if len(context.args) >= 1 and args[0].isdigit():
        try:
            jm_id = args[0]
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text=f'正在获取本子信息...')
            
            # 请求本子实体类
            album: JmAlbumDetail = client.get_album_detail(jm_id)
            name = album.name
            
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text=f'开始下载《{name}》，请稍后...')
            
            # 下载with重试逻辑
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    download_album(jm_id, option)
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    await context.bot.send_message(chat_id=update.effective_chat.id,
                                                   text=f'下载出现问题，正在重试 ({attempt + 1}/{max_retries})...')
                    time.sleep(2)
            
            # 检查下载结果
            download_dir = f'download/{jm_id}'
            if not os.path.exists(download_dir):
                await context.bot.send_message(chat_id=update.effective_chat.id,
                                               text='❌ 下载失败，目录不存在')
                return
            
            # 检查第一张图片
            first_image = f'download/{jm_id}/00001.jpg'
            if os.path.exists(first_image):
                with open(first_image, 'rb') as f:
                    await context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=f,
                        caption=name
                    )
            else:
                await context.bot.send_message(chat_id=update.effective_chat.id,
                                               text='下载完成，但未找到预览图片')
            # 获取所有图片文件并排序
            image_paths = glob.glob(f'./download/{jm_id}/*.jpg')
            # 改进的排序逻辑：按照文件名中的数字排序
            image_paths.sort(key=lambda x: int(re.search(r'(\d+)', x.split('/')[-1]).group()))
            
            # 选择发送方式：Telegraph或直接发送
            if TELEGRAPH_ENABLED and len(image_paths) > TELEGRAPH_THRESHOLD:
                # 图片数量较多时，尝试上传到Telegraph
                await context.bot.send_message(chat_id=update.effective_chat.id,
                                             text=f'图片较多({len(image_paths)}张)，正在尝试上传到Telegraph...')
                
                # 上传少量图片到Telegraph作为示例
                sample_size = min(3, len(image_paths))  # 只上传前3张作为示例
                telegraph_urls = []
                for i in range(sample_size):
                    url = upload_to_telegraph(image_paths[i])
                    if url:
                        telegraph_urls.append(url)
                
                if telegraph_urls:
                    # 创建Telegraph消息
                    telegraph_message = create_telegraph_page(name, telegraph_urls)
                    if telegraph_message:
                        await context.bot.send_message(chat_id=update.effective_chat.id,
                                                     text=f'✅ 预览图片已上传到Telegraph:\n\n{telegraph_message}')
                    
                    # 发送提示消息
                    summary_message = create_image_summary(name, image_paths)
                    if summary_message:
                        await context.bot.send_message(chat_id=update.effective_chat.id,
                                                     text=summary_message)
                    
                    # 继续使用传统方式发送所有图片
                    await send_images_traditional(context, update.effective_chat.id, image_paths)
                else:
                    await context.bot.send_message(chat_id=update.effective_chat.id,
                                                 text='❌ Telegraph上传失败，使用传统方式发送...')
                    await send_images_traditional(context, update.effective_chat.id, image_paths)
            else:
                # 图片数量较少时，或Telegraph已禁用，直接发送
                await send_images_traditional(context, update.effective_chat.id, image_paths)

        except MissingAlbumPhotoException as e:
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text=f'id={e.error_jmid}的本子不存在')
        except JmcomicException as e:
            # 捕获所有异常，用作兜底
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text=f'jmcomic遇到异常: {e}')
    else:
        await update.message.reply_text("请输入一个数字")


if __name__ == '__main__':
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    start_handler = CommandHandler('start', start)
    bind_pica_handler = CommandHandler('bind_pica', bind_pica)
    echo_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), echo)
    jm_search_handler = CommandHandler('jm', jm_search)

    application.add_handler(start_handler)
    application.add_handler(bind_pica_handler)
    application.add_handler(echo_handler)
    application.add_handler(jm_search_handler)

    print("Bot 正在运行...")
    application.run_polling()
