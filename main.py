import glob
import logging
import jmcomic
from jmcomic import *
from telegram import Update, InputMediaPhoto
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, filters, MessageHandler

from options import *

# JM客户端创建
option = jmcomic.create_option_by_file('./option.yml')
client = option.new_jm_client()

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


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text=update.message.text)


async def jm_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(context.args) >= 1 and args[0].isdigit():
        try:
            jm_id = args[0]
            # 请求本子实体类
            album: JmAlbumDetail = client.get_album_detail(jm_id)
            name = album.name
            download_album(jm_id, option)
            # await context.bot.send_photo(chat_id=update.effective_chat.id,
            #                                text=name)
            with open(f'download/{jm_id}/00001.jpg', 'rb') as f:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=f,
                    caption=name
                )
            # # 发送图片，10张打包
            image_paths = glob.glob(f'./download/{jm_id}/*.jpg')
            print(image_paths)
            batch_size = 10
            for i in range(0, len(image_paths), batch_size):
                media_group = []

                for path in image_paths[i:i + batch_size]:
                    with open(path, "rb") as f:
                        media_group.append(InputMediaPhoto(media=f.read()))

                print(media_group)

                if media_group:
                    await context.bot.send_media_group(chat_id=update.effective_chat.id, media=media_group)

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
