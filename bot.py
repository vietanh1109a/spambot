import subprocess
import logging
import threading
import os
import json
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, filters

# Cấu hình logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Dictionary để lưu các process đang chạy
running_processes = {}

# Lấy token từ biến môi trường
TOKEN = os.environ.get("BOT_TOKEN")

# Lấy danh sách nhóm được phép từ biến môi trường hoặc từ file cấu hình
try:
    # Thử đọc từ biến môi trường trước
    allowed_groups_str = os.environ.get("ALLOWED_GROUPS")
    if allowed_groups_str:
        ALLOWED_GROUPS = json.loads(allowed_groups_str)
    else:
        # Nếu không có biến môi trường, thử đọc từ file
        with open('config.json', 'r') as f:
            config = json.load(f)
            ALLOWED_GROUPS = config.get('allowed_groups', [])
except Exception as e:
    logger.warning(f"Không thể đọc danh sách nhóm được phép: {str(e)}")
    # Mặc định nếu không có cấu hình
    ALLOWED_GROUPS = []

def kill_process_after_timeout(process_id, phone_number):
    process = running_processes.get(process_id)
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
        if process_id in running_processes:
            del running_processes[process_id]
        logger.info(f"Đã dừng spam cho số {phone_number} sau 1 phút")

# Decorator để kiểm tra nhóm
def restricted_to_allowed_groups(func):
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        chat_id = update.effective_chat.id
        
        if chat_id not in ALLOWED_GROUPS:
            await update.message.reply_text('Bot này chỉ hoạt động trong các nhóm được chỉ định.')
            logger.warning(f"Người dùng từ chat ID {chat_id} đã cố gắng sử dụng bot")
            return
        
        return await func(update, context, *args, **kwargs)
    
    return wrapped

@restricted_to_allowed_groups
async def spam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text('Vui lòng cung cấp số điện thoại. Ví dụ: /spam 0326992526')
        return
    
    phone_number = context.args[0]
    user_id = update.effective_user.id
    process_id = f"{user_id}_{phone_number}"
    
    # Kiểm tra xem quá trình đã chạy chưa
    if process_id in running_processes:
        await update.message.reply_text(f'Đang có quá trình spam cho số {phone_number}. Vui lòng đợi.')
        return
    
    await update.message.reply_text(f'Đang spam số điện thoại {phone_number}...')
    logger.info(f"Bắt đầu spam số {phone_number} theo yêu cầu từ user {user_id}")
    
    try:
        # Chạy script
        process = subprocess.Popen(['python', 'spamvip.py', phone_number])
        running_processes[process_id] = process
        
        # Tạo một thread để kết thúc process sau 60 giây
        timer = threading.Timer(60.0, kill_process_after_timeout, args=[process_id, phone_number])
        timer.start()
        
        await update.message.reply_text('Spam đang chạy và sẽ tự động dừng sau 1 phút.')
        
    except Exception as e:
        await update.message.reply_text(f'Đã xảy ra lỗi: {str(e)}')
        logger.error(f"Lỗi khi spam số {phone_number}: {str(e)}")
        if process_id in running_processes:
            del running_processes[process_id]

@restricted_to_allowed_groups
async def stop_spam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    
    # Tìm và dừng tất cả các process của người dùng
    processes_to_stop = [pid for pid in running_processes.keys() if pid.startswith(f"{user_id}_")]
    
    if not processes_to_stop:
        await update.message.reply_text('Không có quá trình spam nào đang chạy.')
        return
    
    for process_id in processes_to_stop:
        process = running_processes.get(process_id)
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
            del running_processes[process_id]
    
    await update.message.reply_text('Đã dừng tất cả các quá trình spam của bạn.')
    logger.info(f"User {user_id} đã dừng tất cả các quá trình spam")

async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    await update.message.reply_text(f'ID của chat này là: {chat_id}')
    logger.info(f"Cung cấp ID {chat_id} cho chat")

def main() -> None:
    if not TOKEN:
        logger.error("Không tìm thấy BOT_TOKEN trong biến môi trường!")
        return
        
    # Tạo ứng dụng với token từ biến môi trường
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Đã xóa lệnh start ở đây
    application.add_handler(CommandHandler("spam", spam))
    application.add_handler(CommandHandler("stop", stop_spam))
    application.add_handler(CommandHandler("get_id", get_id))
    
    logger.info("Bot đã khởi động và đang lắng nghe...")
    application.run_polling()

if __name__ == '__main__':
    main()