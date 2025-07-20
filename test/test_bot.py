# 用于测试BOT功能
from telegram import *
from telegram.ext import *
import logging

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)




if __name__ == "__main__":
    app = ApplicationBuilder().token("8044072756:AAGBqm3WuWn-645d73mLHtkXZSW6ipiSg44").build()

    app.run_polling()
