import glob
import logging
import re
import os
import time
import zipfile
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

# 压缩包配置
ENABLE_ZIP_ARCHIVE = True  # 是否在发送完图片后提供压缩包
ZIP_THRESHOLD = 5  # 超过多少张图片时提供压缩包

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


def create_zip_archive(image_paths, zip_name):
    """创建图片压缩包"""
    try:
        zip_path = f"download/{zip_name}.zip"
        
        # 确保下载目录存在
        os.makedirs(os.path.dirname(zip_path), exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for i, image_path in enumerate(image_paths):
                if os.path.exists(image_path):
                    # 获取文件名并重命名为有序的格式
                    file_ext = os.path.splitext(image_path)[1]
                    new_name = f"{i+1:03d}{file_ext}"
                    zipf.write(image_path, new_name)
        
        return zip_path if os.path.exists(zip_path) else None
    except Exception as e:
        print(f"创建压缩包失败: {e}")
        return None

def get_file_size_mb(file_path):
    """获取文件大小（MB）"""
    try:
        return os.path.getsize(file_path) / (1024 * 1024)
    except:
        return 0


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
            
            # 发送图片
            if len(image_paths) > 10:
                await context.bot.send_message(chat_id=update.effective_chat.id,
                                             text=f'图片较多({len(image_paths)}张)，将分批发送...')
            
            # 发送所有图片
            await send_images_traditional(context, update.effective_chat.id, image_paths)
            
            # 如果图片数量超过阈值，创建并发送压缩包
            if ENABLE_ZIP_ARCHIVE and len(image_paths) > ZIP_THRESHOLD:
                await context.bot.send_message(chat_id=update.effective_chat.id,
                                             text='📦 正在创建压缩包...')
                
                zip_path = create_zip_archive(image_paths, f"{name}_{jm_id}")
                if zip_path:
                    file_size = get_file_size_mb(zip_path)
                    
                    # Telegram文件大小限制是50MB
                    if file_size <= 50:
                        try:
                            with open(zip_path, 'rb') as zip_file:
                                await context.bot.send_document(
                                    chat_id=update.effective_chat.id,
                                    document=zip_file,
                                    filename=f"{name}.zip",
                                    caption=f"📦 完整压缩包\n📊 大小: {file_size:.1f}MB\n📷 包含: {len(image_paths)}张图片"
                                )
                            
                            # 发送完成后删除压缩包
                            os.remove(zip_path)
                            
                        except Exception as e:
                            await context.bot.send_message(chat_id=update.effective_chat.id,
                                                         text=f'❌ 发送压缩包失败: {str(e)}')
                    else:
                        await context.bot.send_message(chat_id=update.effective_chat.id,
                                                     text=f'❌ 压缩包太大({file_size:.1f}MB)，超过Telegram 50MB限制')
                        # 删除过大的压缩包
                        os.remove(zip_path)
                else:
                    await context.bot.send_message(chat_id=update.effective_chat.id,
                                                 text='❌ 创建压缩包失败')

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
