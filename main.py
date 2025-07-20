import glob
import math
import logging
import re
import os
import time
import zipfile
import json
import datetime
import threading
import shutil
import jmcomic
from jmcomic import *
from telegram import *
from telegram.ext import *

# 尝试加载.env文件
def load_env_file():
    """加载.env文件中的环境变量"""
    env_file = '.env'
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

# 环境变量配置
def get_env_bool(key, default=False):
    """获取布尔型环境变量"""
    value = os.getenv(key, str(default)).lower()
    return value in ('true', '1', 'yes', 'on')

def get_env_int(key, default=0):
    """获取整型环境变量"""
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default

def get_env_float(key, default=0.0):
    """获取浮点型环境变量"""
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default

# 加载环境变量文件
load_env_file()

# Bot配置
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")

# JM客户端配置
JM_RETRY_TIMES = get_env_int('JM_RETRY_TIMES', 2)  # 减少重试次数
JM_TIMEOUT = get_env_int('JM_TIMEOUT', 15)  # 减少超时时间

# 压缩包配置
ENABLE_ZIP_ARCHIVE = get_env_bool('ENABLE_ZIP_ARCHIVE', True)
ZIP_THRESHOLD = get_env_int('ZIP_THRESHOLD', 5)

# 存储管理配置
ENABLE_STORAGE_MANAGEMENT = get_env_bool('ENABLE_STORAGE_MANAGEMENT', True)
MAX_STORAGE_SIZE_GB = get_env_float('MAX_STORAGE_SIZE_GB', 2.0)
KEEP_DAYS = get_env_int('KEEP_DAYS', 7)
CLEANUP_INTERVAL_HOURS = get_env_int('CLEANUP_INTERVAL_HOURS', 6)
CACHE_DB_PATH = os.getenv('CACHE_DB_PATH', 'download/cache.db')

# 下载进度配置
SHOW_DOWNLOAD_PROGRESS = get_env_bool('SHOW_DOWNLOAD_PROGRESS', True)
PROGRESS_UPDATE_INTERVAL = get_env_int('PROGRESS_UPDATE_INTERVAL', 5)

# JM客户端创建
def create_jm_option():
    """创建JM配置，用于下载操作"""
    try:
        # 首先尝试使用内置的option.yml
        if os.path.exists('./option.yml') and os.path.isfile('./option.yml'):
            option = jmcomic.create_option_by_file('./option.yml')
            # 添加重试和超时配置
            option.client.retry_times = JM_RETRY_TIMES
            option.client.timeout = JM_TIMEOUT
            print("✅ 使用内置配置文件: ./option.yml")
            return option
    except Exception as e:
        print(f"⚠️ 无法读取内置配置文件: {e}")
    
    # 如果配置文件失败，使用代码创建默认配置
    print("ℹ️ 使用默认配置创建选项")
    try:
        # 创建默认配置
        option = jmcomic.create_option(
            base_dir='./download/',
            dir_rule='Bd / Pid',
            download_config={
                'image': {'suffix': '.jpg'}
            }
        )
        option.client.retry_times = JM_RETRY_TIMES
        option.client.timeout = JM_TIMEOUT
        return option
    except Exception as e:
        print(f"❌ 创建默认配置失败: {e}")
        # 最后的兜底方案
        option = jmcomic.create_option()
        option.client.retry_times = JM_RETRY_TIMES
        option.client.timeout = JM_TIMEOUT
        return option

# 创建全局配置和客户端
jm_option = create_jm_option()
client = jm_option.new_jm_client()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


# From DeathofBrain: dev分支要不弄个beta bot？存储管理器有做单元测试吗？
class StorageManager:
    """存储管理器 - 简化版，仅负责缓存和清理"""
    
    def __init__(self):
        self.cache_file = CACHE_DB_PATH
        self.init_cache_tracking()
        self.start_cleanup_scheduler()
    
    def init_cache_tracking(self):
        """初始化缓存跟踪文件"""
        if CACHE_DB_PATH.endswith('.db'):
            # 使用简单的JSON文件而不是数据库
            self.cache_file = CACHE_DB_PATH.replace('.db', '.json')
        else:
            self.cache_file = CACHE_DB_PATH
        
        # 确保目录存在
        cache_dir = os.path.dirname(self.cache_file)
        if cache_dir:  # 只有当目录不为空时才创建
            os.makedirs(cache_dir, exist_ok=True)
        
        if not os.path.exists(self.cache_file):
            with open(self.cache_file, 'w') as f:
                json.dump({}, f)
    
    def record_download(self, jm_id, name, file_count, folder_size):
        """记录下载到缓存"""
        now = datetime.datetime.now().isoformat()
        
        try:
            with open(self.cache_file, 'r') as f:
                cache_data = json.load(f)
        except:
            cache_data = {}
        
        cache_data[jm_id] = {
            'name': name,
            'download_time': now,
            'access_time': now,
            'file_count': file_count,
            'folder_size_bytes': folder_size
        }
        
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
        except Exception as e:
            print(f"缓存记录失败: {e}")
    
    def is_cached(self, jm_id):
        """检查是否已缓存"""
        download_path = f'download/{jm_id}'
        if not os.path.exists(download_path):
            return False
        
        # 更新访问时间
        try:
            with open(self.cache_file, 'r') as f:
                cache_data = json.load(f)
            
            if jm_id in cache_data:
                cache_data[jm_id]['access_time'] = datetime.datetime.now().isoformat()
                
                with open(self.cache_file, 'w') as f:
                    json.dump(cache_data, f, indent=2)
        except Exception as e:
            print(f"更新访问时间失败: {e}")
        
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
            
            # 读取缓存数据
            try:
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
            except:
                cache_data = {}
            
            # 获取需要清理的项目
            items_to_clean = []
            for jm_id, data in cache_data.items():
                try:
                    access_time = datetime.datetime.fromisoformat(data['access_time'])
                    if access_time < cutoff_time or total_size > max_size_bytes:
                        items_to_clean.append((jm_id, access_time, data.get('folder_size_bytes', 0)))
                except:
                    continue
            
            # 按访问时间排序（最旧的先清理）
            items_to_clean.sort(key=lambda x: x[1])
            
            cleaned_count = 0
            freed_space = 0
            
            for jm_id, access_time, folder_size in items_to_clean:
                folder_path = f'download/{jm_id}'
                if os.path.exists(folder_path):
                    try:
                        shutil.rmtree(folder_path)
                        freed_space += folder_size or 0
                        cleaned_count += 1
                        
                        # 从缓存删除记录
                        if jm_id in cache_data:
                            del cache_data[jm_id]
                        
                        # 如果释放了足够空间，停止清理
                        if total_size - freed_space <= max_size_bytes:
                            break
                    except Exception as e:
                        print(f"清理失败 {jm_id}: {e}")
            
            # 更新缓存文件
            if cleaned_count > 0:
                try:
                    with open(self.cache_file, 'w') as f:
                        json.dump(cache_data, f, indent=2)
                except:
                    pass
                
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

# 初始化存储管理器
storage_manager = StorageManager()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_msg = "欢迎使用DouJin机器人！为您自动获取指定本子哟，祝起飞愉快~⭐"
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

# TODO: 抽象化下载逻辑
# 下载指定章节本子 返回值：图片路径数组
def jm_download(jm_id, jm_option):
    download_dir = f'download/{jm_id}'
    # is_cached = storage_manager.is_cached(jm_id)
    # if not is_cached:
        # 如果未缓存，下载本子
    download_photo(jm_id, jm_option)
        # # 记录下载到缓存
        # folder_size = storage_manager.get_folder_size(download_dir)
        # storage_manager.record_download(jm_id, jm_option.album_name, len(image_paths), folder_size)
        
    image_paths = glob.glob(f'{download_dir}/*.jpg')
    image_paths.sort(key=lambda x: int(re.search(r'(\d+)', x.split('/')[-1]).group()))
    return image_paths

'''
函数结果：
自成一章：直接下载并发送，无需回调
单本多章节：输出章节列表，用户选择后下载指定章节，下载与发送在回调中实现
'''
async def jm_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 获取指令后参数
    args = context.args
    
    # 如果是jm_id
    if len(context.args) >= 1 and args[0].isdigit():
        try:
            jm_id = args[0]
            # jm_photo_id = ''
            # 逻辑：先获取本子类，再输出标题，章节内容，最后根据按钮回调发送相关章节
            # 请求本子实体类
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text=f'正在获取本子信息...')
            
            album: JmAlbumDetail = client.get_album_detail(jm_id)
            if not album.is_album():
                await context.bot.send_message(chat_id=update.effective_chat.id,
                                               text='❌ 该ID不是一个有效的本子')
                return
            
            name = album.name
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text=f'开始下载《{name}》，请稍后...')
            image_paths = []
            # 检查是否为单章节
            # 若是，直接下载
            if len(album.episode_list) == 1:
                try:
                    image_paths = jm_download(jm_id, jm_option)
                    # 检查下载结果
                    if not image_paths:
                        await context.bot.send_message(chat_id=update.effective_chat.id,
                                                       text='❌ 下载失败，未找到图片文件')
                        return
                    # 处理和发送图片
                    await process_and_send_images(context, update.effective_chat.id, jm_id, name, image_paths)
                    
                except Exception as e:
                    await context.bot.send_message(chat_id=update.effective_chat.id,
                                                   text=f'❌ 下载失败: {str(e)}')
                    return
            # 否则，输出章节按钮列表（20个为一组）
            else:
                await episode_button_send(update, context, album)
            
        except JmcomicException as e:
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text=f'jmcomic遇到异常: {e}')
        # 捕获所有异常，用作兜底
        # 别忘了保存log
        except Exception as e:
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text=f'发生错误: {str(e)}')
    # TODO: 本子名称搜索实现
    else:
        await update.message.reply_text("请输入一个数字")

# 暂使用全局变量，后续通过类来管理
episode_buttons = []
index = 0
max_index = 0
nav_buttons = [
    InlineKeyboardButton(text="首页", callback_data="first"),
    InlineKeyboardButton(text="上一页", callback_data="prev"),
    InlineKeyboardButton(text="下一页", callback_data="next"),
    InlineKeyboardButton(text="末页", callback_data="last")
]

# 章节按钮发送
async def episode_button_send(update: Update, context: ContextTypes.DEFAULT_TYPE, album: JmAlbumDetail):
    global index, max_index, episode_buttons
    # 初始化章节按钮列表
    episode_buttons.clear()
    index = 0
    # 计算最大页数
    max_index = math.ceil(len(album.episode_list) / 20)
    for episode in album.episode_list:
        episode_id, episode_name = episode[0], episode[2] or episode[1]
        # 创建按钮
        button = InlineKeyboardButton(text=f"{episode_name}", callback_data=episode_id)
        episode_buttons.append(button)
    # 取前二十个按钮，再加上导航按钮
    buttons = episode_buttons[:20] + nav_buttons
    # 分割按钮为n行四列
    rows = [episode_buttons[i:i + 4] for i in range(0, len(episode_buttons[:20]), 4)]
    rows.append(nav_buttons)  # 添加导航按钮作为最后一行
    # N行四列排布
    keyboards = InlineKeyboardMarkup(rows)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"本子《{album.title}》包含{len(album.episode_list)}个章节，请选择章节下载：",
        reply_markup=keyboards
    )
    
# 章节按钮回调
async def episode_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # 确认回调
    # 处理章节ID下载
    jm_id = query.data
    try:
        image_paths = jm_download(jm_id, jm_option)
        # 检查下载结果
        if not image_paths:
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                            text='❌ 下载失败，未找到图片文件')
            return
        # 处理和发送图片
        await process_and_send_images(context, update.effective_chat.id, jm_id, None, image_paths)
        
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                        text=f'❌ 下载失败: {str(e)}')
        return
            
# 导航按钮回调
async def episode_nav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # 确认回调
    global index, max_index, episode_buttons
    
    if query.data == "first":
        index = 0
    elif query.data == "prev":
        index = max(0, index - 1)
    elif query.data == "next":
        index = min(max_index - 1, index + 1)
    elif query.data == "last":
        index = max_index - 1
    
    # 更新按钮显示
    start = index * 20
    end = start + 20
    buttons = episode_buttons[start:end]
    
    # 分割按钮为n行四列
    rows = [buttons[i:i + 4] for i in range(0, len(buttons), 4)]
    
    # 添加导航按钮作为最后一行
    rows.append(nav_buttons)
    
    # 更新消息
    await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(rows))
        

async def process_and_send_images(context, chat_id, jm_id, name, image_paths):
    """处理和发送图片的统一函数"""
    try:
        # 发送图片
        if len(image_paths) > 10:
            await context.bot.send_message(chat_id=chat_id,
                                         text=f'图片较多({len(image_paths)}张)，将分批发送...')
        # 发送第一张图片作为预览
        if name:
            with open(image_paths[0], 'rb') as f:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=f,
                    caption=f"📋 {name} (共{len(image_paths)}张)"
                )
        
        # 发送所有图片
        
        await send_images_traditional(context, chat_id, image_paths)
        
        # # 如果图片数量超过阈值，创建并发送压缩包
        # if ENABLE_ZIP_ARCHIVE and len(image_paths) > ZIP_THRESHOLD:
        #     await context.bot.send_message(chat_id=chat_id,
        #                                  text='📦 正在创建压缩包...')
            
        #     if name:
        #         zip_path = create_zip_archive(image_paths, f"{name}_{jm_id}")
        #     else:
        #         zip_path = create_zip_archive(image_paths, f"{jm_id}")
        #     if zip_path:
        #         file_size = get_file_size_mb(zip_path)
                
        #         # Telegram文件大小限制是50MB
        #         if file_size <= 50:
        #             try:
        #                 with open(zip_path, 'rb') as zip_file:
        #                     await context.bot.send_document(
        #                         chat_id=chat_id,
        #                         document=zip_file,
        #                         filename=f"{name}.zip",
        #                         caption=f"📦 完整压缩包\n📊 大小: {file_size:.1f}MB\n📷 包含: {len(image_paths)}张图片"
        #                     )
                        
        #                 # 发送完成后删除压缩包
        #                 os.remove(zip_path)
                        
        #             except Exception as e:
        #                 await context.bot.send_message(chat_id=chat_id,
        #                                              text=f'❌ 发送压缩包失败: {str(e)}')
        #         else:
        #             await context.bot.send_message(chat_id=chat_id,
        #                                          text=f'❌ 压缩包太大({file_size:.1f}MB)，超过Telegram 50MB限制')
        #             # 删除过大的压缩包
        #             os.remove(zip_path)
        #     else:
        #         await context.bot.send_message(chat_id=chat_id,
        #                                      text='❌ 创建压缩包失败')
        
        # 发送完成提示
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ 处理完成\n📚 《{name}》\n📷 共 {len(image_paths)} 张图片"
        )
        
    except Exception as e:
        print(e)
        await context.bot.send_message(chat_id=chat_id,
                                     text=f'处理图片时发生错误: {str(e)}')


if __name__ == '__main__':
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # 命令处理器
    start_handler = CommandHandler('start', start)
    bind_pica_handler = CommandHandler('bind_pica', bind_pica)
    cleanup_handler = CommandHandler('cleanup', cleanup_command)
    jm_search_handler = CommandHandler('jm', jm_search)
    echo_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), echo)

    # 注册处理器
    application.add_handler(start_handler)
    application.add_handler(bind_pica_handler)
    application.add_handler(cleanup_handler)
    application.add_handler(jm_search_handler)
    application.add_handler(echo_handler)
    application.add_handler(CallbackQueryHandler(episode_button_callback, pattern=r'^\d+$'))  # 章节按钮回调
    application.add_handler(CallbackQueryHandler(episode_nav_callback, pattern=r'^(first|prev|next|last)$'))  # 导航按钮回调

    print("🤖 Bot 启动中...")
    print(f"📁 存储管理: {'启用' if ENABLE_STORAGE_MANAGEMENT else '禁用'}")
    print(f"💾 最大存储: {MAX_STORAGE_SIZE_GB}GB")
    print(f"🧹 保留天数: {KEEP_DAYS}天")
    print(f"📦 压缩包功能: {'启用' if ENABLE_ZIP_ARCHIVE else '禁用'}")
    print("✅ Bot 运行中...")
    
    application.run_polling()
