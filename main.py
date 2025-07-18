import glob
import logging
import re
import requests
import json
import jmcomic
from jmcomic import *
from telegram import Update, InputMediaPhoto
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, filters, MessageHandler

from options import *

# JM客户端创建
option = jmcomic.create_option_by_file('./option.yml')
client = option.new_jm_client()

# Telegraph功能开关 (当Telegraph服务不可用时可以关闭)
TELEGRAPH_ENABLED = True
TELEGRAPH_THRESHOLD = 10  # 超过多少张图片时使用Telegraph

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
        with open(image_path, 'rb') as f:
            url = 'https://telegra.ph/upload'
            files = {'file': ('file', f, 'image/jpeg')}
            response = requests.post(url, files=files, timeout=30)
            if response.status_code == 200:
                result = json.loads(response.content)
                return f'https://telegra.ph{result[0]["src"]}'
            else:
                return None
    except Exception as e:
        print(f"上传到Telegraph失败: {e}")
        return None


def create_telegraph_page(title, image_urls):
    """创建Telegraph页面包含所有图片"""
    try:
        # 构建页面内容
        content = []
        for i, url in enumerate(image_urls, 1):
            content.extend([
                {'tag': 'figure', 'children': [
                    {'tag': 'img', 'attrs': {'src': url}},
                    {'tag': 'figcaption', 'children': [f'第{i}页']}
                ]},
                {'tag': 'br'}
            ])
        
        # 创建Telegraph页面
        telegraph_data = {
            'title': title,
            'content': json.dumps(content),
            'return_content': 'true'
        }
        
        response = requests.post('https://api.telegra.ph/createPage', data=telegraph_data, timeout=30)
        if response.status_code == 200:
            result = response.json()
            if result['ok']:
                return f"https://telegra.ph/{result['result']['path']}"
        return None
    except Exception as e:
        print(f"创建Telegraph页面失败: {e}")
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
            # 请求本子实体类
            album: JmAlbumDetail = client.get_album_detail(jm_id)
            name = album.name
            download_album(jm_id, option)
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text=f'正在获取，请稍后…')
            # await context.bot.send_photo(chat_id=update.effective_chat.id,
            #                                text=name)
            with open(f'download/{jm_id}/00001.jpg', 'rb') as f:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=f,
                    caption=name
                )
            # 获取所有图片文件并排序
            image_paths = glob.glob(f'./download/{jm_id}/*.jpg')
            # 改进的排序逻辑：按照文件名中的数字排序
            image_paths.sort(key=lambda x: int(re.search(r'(\d+)', x.split('/')[-1]).group()))
            
            # 选择发送方式：Telegraph或直接发送
            if TELEGRAPH_ENABLED and len(image_paths) > TELEGRAPH_THRESHOLD:
                # 图片数量较多时，尝试上传到Telegraph
                await context.bot.send_message(chat_id=update.effective_chat.id,
                                             text=f'图片较多({len(image_paths)}张)，正在上传到Telegraph...')
                
                # 上传所有图片到Telegraph
                telegraph_urls = []
                for path in image_paths:
                    url = upload_to_telegraph(path)
                    if url:
                        telegraph_urls.append(url)
                
                if telegraph_urls:
                    # 创建Telegraph页面
                    telegraph_page = create_telegraph_page(name, telegraph_urls)
                    if telegraph_page:
                        await context.bot.send_message(chat_id=update.effective_chat.id,
                                                     text=f'✅ 已上传到Telegraph：{telegraph_page}')
                    else:
                        await context.bot.send_message(chat_id=update.effective_chat.id,
                                                     text='❌ 创建Telegraph页面失败，使用传统方式发送...')
                        # 回退到原有方式
                        await send_images_traditional(context, update.effective_chat.id, image_paths)
                else:
                    await context.bot.send_message(chat_id=update.effective_chat.id,
                                                 text='❌ 上传Telegraph失败，使用传统方式发送...')
                    # 回退到原有方式
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
