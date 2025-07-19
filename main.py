import glob
import logging
import re
import os
import time
import zipfile
import json
import sqlite3
import datetime
import threading
import shutil
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

# 存储管理配置
ENABLE_STORAGE_MANAGEMENT = True  # 启用存储管理
MAX_STORAGE_SIZE_GB = 2.0  # 最大存储空间（GB）
KEEP_DAYS = 7  # 保留天数
CLEANUP_INTERVAL_HOURS = 6  # 清理检查间隔（小时）
CACHE_DB_PATH = 'download/cache.db'  # 缓存数据库路径

# 下载进度配置
SHOW_DOWNLOAD_PROGRESS = True  # 显示下载进度
PROGRESS_UPDATE_INTERVAL = 5  # 进度更新间隔（张图片）

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


class StorageManager:
    """存储管理器"""
    
    def __init__(self):
        self.db_path = CACHE_DB_PATH
        self.init_database()
        self.start_cleanup_scheduler()
    
    def init_database(self):
        """初始化数据库"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS downloads (
                    jm_id TEXT PRIMARY KEY,
                    name TEXT,
                    download_time TIMESTAMP,
                    access_time TIMESTAMP,
                    file_count INTEGER,
                    folder_size_bytes INTEGER,
                    user_id INTEGER
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_stats (
                    user_id INTEGER PRIMARY KEY,
                    total_downloads INTEGER DEFAULT 0,
                    last_download_time TIMESTAMP,
                    total_images_downloaded INTEGER DEFAULT 0
                )
            ''')
    
    def record_download(self, jm_id, name, user_id, file_count, folder_size):
        """记录下载"""
        now = datetime.datetime.now()
        
        with sqlite3.connect(self.db_path) as conn:
            # 记录下载
            conn.execute('''
                INSERT OR REPLACE INTO downloads 
                (jm_id, name, download_time, access_time, file_count, folder_size_bytes, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (jm_id, name, now, now, file_count, folder_size, user_id))
            
            # 更新用户统计
            conn.execute('''
                INSERT OR REPLACE INTO user_stats 
                (user_id, total_downloads, last_download_time, total_images_downloaded)
                VALUES (?, 
                    COALESCE((SELECT total_downloads FROM user_stats WHERE user_id = ?), 0) + 1,
                    ?,
                    COALESCE((SELECT total_images_downloaded FROM user_stats WHERE user_id = ?), 0) + ?
                )
            ''', (user_id, user_id, now, user_id, file_count))
    
    def is_cached(self, jm_id):
        """检查是否已缓存"""
        download_path = f'download/{jm_id}'
        if not os.path.exists(download_path):
            return False
        
        # 更新访问时间
        now = datetime.datetime.now()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE downloads SET access_time = ? WHERE jm_id = ?
            ''', (now, jm_id))
        
        return True
    
    def get_folder_size(self, folder_path):
        """获取文件夹大小"""
        total = 0
        try:
            for dirpath, dirnames, filenames in os.walk(folder_path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    total += os.path.getsize(filepath)
        except:
            pass
        return total
    
    def get_total_storage_size(self):
        """获取总存储大小"""
        return self.get_folder_size('download')
    
    def cleanup_old_files(self):
        """清理旧文件"""
        if not ENABLE_STORAGE_MANAGEMENT:
            return
        
        try:
            now = datetime.datetime.now()
            cutoff_time = now - datetime.timedelta(days=KEEP_DAYS)
            total_size = self.get_total_storage_size()
            max_size_bytes = MAX_STORAGE_SIZE_GB * 1024 * 1024 * 1024
            
            with sqlite3.connect(self.db_path) as conn:
                # 获取需要清理的项目（按访问时间排序）
                cursor = conn.execute('''
                    SELECT jm_id, folder_size_bytes FROM downloads 
                    WHERE access_time < ? OR ? > ?
                    ORDER BY access_time ASC
                ''', (cutoff_time, total_size, max_size_bytes))
                
                cleaned_count = 0
                freed_space = 0
                
                for jm_id, folder_size in cursor.fetchall():
                    folder_path = f'download/{jm_id}'
                    if os.path.exists(folder_path):
                        try:
                            shutil.rmtree(folder_path)
                            freed_space += folder_size or 0
                            cleaned_count += 1
                            
                            # 从数据库删除记录
                            conn.execute('DELETE FROM downloads WHERE jm_id = ?', (jm_id,))
                            
                            # 如果释放了足够空间，停止清理
                            if total_size - freed_space <= max_size_bytes:
                                break
                        except Exception as e:
                            print(f"清理失败 {jm_id}: {e}")
                
                if cleaned_count > 0:
                    print(f"清理完成: 删除了{cleaned_count}个文件夹，释放了{freed_space/1024/1024:.1f}MB空间")
        
        except Exception as e:
            print(f"清理过程出错: {e}")
    
    def start_cleanup_scheduler(self):
        """启动清理调度器"""
        def cleanup_worker():
            while True:
                time.sleep(CLEANUP_INTERVAL_HOURS * 3600)
                self.cleanup_old_files()
        
        if ENABLE_STORAGE_MANAGEMENT:
            cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
            cleanup_thread.start()
    
    def get_user_stats(self, user_id):
        """获取用户统计"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT total_downloads, last_download_time, total_images_downloaded 
                FROM user_stats WHERE user_id = ?
            ''', (user_id,))
            
            result = cursor.fetchone()
            if result:
                return {
                    'total_downloads': result[0],
                    'last_download_time': result[1],
                    'total_images_downloaded': result[2]
                }
            return None

# 初始化存储管理器
storage_manager = StorageManager()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_stats = storage_manager.get_user_stats(update.effective_user.id)
    
    welcome_msg = "欢迎使用DouJin机器人！为您自动获取指定本子哟，祝起飞愉快~⭐"
    
    if user_stats:
        welcome_msg += f"\n\n📊 您的统计:\n"
        welcome_msg += f"📚 总下载: {user_stats['total_downloads']}个\n"
        welcome_msg += f"🖼️ 总图片: {user_stats['total_images_downloaded']}张"
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=welcome_msg)


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


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """显示用户统计和系统状态"""
    user_id = update.effective_user.id
    user_stats = storage_manager.get_user_stats(user_id)
    
    # 系统存储信息
    total_size = storage_manager.get_total_storage_size()
    total_size_mb = total_size / (1024 * 1024)
    max_size_mb = MAX_STORAGE_SIZE_GB * 1024
    
    msg = f"📊 **统计信息**\n\n"
    
    if user_stats:
        msg += f"👤 **您的统计:**\n"
        msg += f"📚 总下载: {user_stats['total_downloads']}个\n"
        msg += f"🖼️ 总图片: {user_stats['total_images_downloaded']}张\n"
        if user_stats['last_download_time']:
            msg += f"🕒 最后下载: {user_stats['last_download_time'][:19]}\n"
    else:
        msg += f"👤 **您还没有下载记录**\n"
    
    msg += f"\n🗄️ **系统存储:**\n"
    msg += f"💾 当前使用: {total_size_mb:.1f}MB / {max_size_mb:.0f}MB\n"
    msg += f"📁 保留期限: {KEEP_DAYS}天\n"
    msg += f"🧹 清理间隔: {CLEANUP_INTERVAL_HOURS}小时\n"
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')


async def cleanup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """手动触发清理"""
    await context.bot.send_message(chat_id=update.effective_chat.id, text="🧹 开始清理旧文件...")
    
    try:
        storage_manager.cleanup_old_files()
        
        # 获取清理后的存储信息
        total_size = storage_manager.get_total_storage_size()
        total_size_mb = total_size / (1024 * 1024)
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"✅ 清理完成\n💾 当前存储: {total_size_mb:.1f}MB"
        )
    except Exception as e:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ 清理失败: {str(e)}"
        )


async def jm_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 获取指令后参数
    args = context.args
    user_id = update.effective_user.id
    
    # 如果是jm_id
    if len(context.args) >= 1 and args[0].isdigit():
        try:
            jm_id = args[0]
            
            # 检查是否已缓存
            if storage_manager.is_cached(jm_id):
                await context.bot.send_message(chat_id=update.effective_chat.id,
                                               text=f'🎯 发现缓存，快速加载中...')
                
                # 获取缓存的信息
                download_dir = f'download/{jm_id}'
                image_paths = glob.glob(f'{download_dir}/*.jpg')
                image_paths.sort(key=lambda x: int(re.search(r'(\d+)', x.split('/')[-1]).group()))
                
                if image_paths:
                    # 发送第一张图片作为预览
                    with open(image_paths[0], 'rb') as f:
                        await context.bot.send_photo(
                            chat_id=update.effective_chat.id,
                            photo=f,
                            caption=f"📋 缓存内容 (共{len(image_paths)}张)"
                        )
                    
                    # 继续处理发送逻辑
                    await process_and_send_images(context, update.effective_chat.id, user_id, jm_id, "缓存内容", image_paths)
                    return
            
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text=f'正在获取本子信息...')
            
            # 请求本子实体类
            album: JmAlbumDetail = client.get_album_detail(jm_id)
            name = album.name
            
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text=f'开始下载《{name}》，请稍后...')
            
            # 下载with重试逻辑和进度显示
            max_retries = 3
            download_success = False
            
            for attempt in range(max_retries):
                try:
                    if SHOW_DOWNLOAD_PROGRESS and attempt == 0:
                        progress_msg = await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text="📊 下载进度: 0%"
                        )
                    
                    download_album(jm_id, option)
                    download_success = True
                    break
                    
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    await context.bot.send_message(chat_id=update.effective_chat.id,
                                                   text=f'下载出现问题，正在重试 ({attempt + 1}/{max_retries})...')
                    time.sleep(2)
            
            if not download_success:
                await context.bot.send_message(chat_id=update.effective_chat.id,
                                               text='❌ 下载失败，已达到最大重试次数')
                return
            
            # 检查下载结果
            download_dir = f'download/{jm_id}'
            if not os.path.exists(download_dir):
                await context.bot.send_message(chat_id=update.effective_chat.id,
                                               text='❌ 下载失败，目录不存在')
                return
            
            # 获取所有图片文件并排序
            image_paths = glob.glob(f'{download_dir}/*.jpg')
            image_paths.sort(key=lambda x: int(re.search(r'(\d+)', x.split('/')[-1]).group()))
            
            if not image_paths:
                await context.bot.send_message(chat_id=update.effective_chat.id,
                                               text='❌ 下载失败，未找到图片文件')
                return
            
            # 记录下载到缓存
            folder_size = storage_manager.get_folder_size(download_dir)
            storage_manager.record_download(jm_id, name, user_id, len(image_paths), folder_size)
            
            # 发送第一张图片作为预览
            with open(image_paths[0], 'rb') as f:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=f,
                    caption=f"📋 {name} (共{len(image_paths)}张)"
                )
            
            # 处理和发送图片
            await process_and_send_images(context, update.effective_chat.id, user_id, jm_id, name, image_paths)

        except MissingAlbumPhotoException as e:
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text=f'id={e.error_jmid}的本子不存在')
        except JmcomicException as e:
            # 捕获所有异常，用作兜底
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text=f'jmcomic遇到异常: {e}')
        except Exception as e:
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text=f'发生错误: {str(e)}')
    else:
        await update.message.reply_text("请输入一个数字")


async def process_and_send_images(context, chat_id, user_id, jm_id, name, image_paths):
    """处理和发送图片的统一函数"""
    try:
        # 发送图片
        if len(image_paths) > 10:
            await context.bot.send_message(chat_id=chat_id,
                                         text=f'图片较多({len(image_paths)}张)，将分批发送...')
        
        # 发送所有图片
        await send_images_traditional(context, chat_id, image_paths)
        
        # 如果图片数量超过阈值，创建并发送压缩包
        if ENABLE_ZIP_ARCHIVE and len(image_paths) > ZIP_THRESHOLD:
            await context.bot.send_message(chat_id=chat_id,
                                         text='📦 正在创建压缩包...')
            
            zip_path = create_zip_archive(image_paths, f"{name}_{jm_id}")
            if zip_path:
                file_size = get_file_size_mb(zip_path)
                
                # Telegram文件大小限制是50MB
                if file_size <= 50:
                    try:
                        with open(zip_path, 'rb') as zip_file:
                            await context.bot.send_document(
                                chat_id=chat_id,
                                document=zip_file,
                                filename=f"{name}.zip",
                                caption=f"📦 完整压缩包\n📊 大小: {file_size:.1f}MB\n📷 包含: {len(image_paths)}张图片"
                            )
                        
                        # 发送完成后删除压缩包
                        os.remove(zip_path)
                        
                    except Exception as e:
                        await context.bot.send_message(chat_id=chat_id,
                                                     text=f'❌ 发送压缩包失败: {str(e)}')
                else:
                    await context.bot.send_message(chat_id=chat_id,
                                                 text=f'❌ 压缩包太大({file_size:.1f}MB)，超过Telegram 50MB限制')
                    # 删除过大的压缩包
                    os.remove(zip_path)
            else:
                await context.bot.send_message(chat_id=chat_id,
                                             text='❌ 创建压缩包失败')
        
        # 发送完成提示
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ 处理完成\n📚 《{name}》\n📷 共 {len(image_paths)} 张图片"
        )
        
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id,
                                     text=f'处理图片时发生错误: {str(e)}')


if __name__ == '__main__':
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # 命令处理器
    start_handler = CommandHandler('start', start)
    bind_pica_handler = CommandHandler('bind_pica', bind_pica)
    stats_handler = CommandHandler('stats', stats_command)
    cleanup_handler = CommandHandler('cleanup', cleanup_command)
    jm_search_handler = CommandHandler('jm', jm_search)
    echo_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), echo)

    # 注册处理器
    application.add_handler(start_handler)
    application.add_handler(bind_pica_handler)
    application.add_handler(stats_handler)
    application.add_handler(cleanup_handler)
    application.add_handler(jm_search_handler)
    application.add_handler(echo_handler)

    print("🤖 Bot 启动中...")
    print(f"📁 存储管理: {'启用' if ENABLE_STORAGE_MANAGEMENT else '禁用'}")
    print(f"💾 最大存储: {MAX_STORAGE_SIZE_GB}GB")
    print(f"🧹 保留天数: {KEEP_DAYS}天")
    print(f"📦 压缩包功能: {'启用' if ENABLE_ZIP_ARCHIVE else '禁用'}")
    print("✅ Bot 运行中...")
    
    application.run_polling()
