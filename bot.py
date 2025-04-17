import subprocess
import logging
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Dictionary để lưu các process đang chạy
running_processes = {}

# Danh sách ID nhóm được phép sử dụng bot
# Thay các số này bằng ID thực tế của nhóm bạn
ALLOWED_GROUPS = [-1002541392300]  # Ví dụ ID nhóm

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
        print(f"Đã dừng spam cho số {phone_number} sau 1 phút")

# Decorator để kiểm tra nhóm
def restricted_to_allowed_groups(func):
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        chat_id = update.effective_chat.id
        
        if chat_id not in ALLOWED_GROUPS:
            await update.message.reply_text('Bot này chỉ hoạt động trong các nhóm được chỉ định.')
            return
        
        return await func(update, context, *args, **kwargs)
    
    return wrapped

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if chat_id in ALLOWED_GROUPS:
        await update.message.reply_text('Chào bạn! Sử dụng /spam <số điện thoại> để bắt đầu spam.')
    else:
        await update.message.reply_text('Bot này chỉ hoạt động trong các nhóm được chỉ định.')

@restricted_to_allowed_groups
async def spam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text('Vui lòng cung cấp số điện thoại. Ví dụ: /spam 0123456789')
        return
    
    phone_number = context.args[0]
    user_id = update.effective_user.id
    process_id = f"{user_id}_{phone_number}"
    
    # Kiểm tra xem quá trình đã chạy chưa
    if process_id in running_processes:
        await update.message.reply_text(f'Đang có quá trình spam cho số {phone_number}. Vui lòng đợi.')
        return
    
    await update.message.reply_text(f'Đang spam số điện thoại {phone_number}...')
    
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

def main() -> None:
    application = ApplicationBuilder().token('7974287093:AAGPbhZi8onuloPbu_7c_O6kxaLW87gS-4E').build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("spam", spam))
    application.add_handler(CommandHandler("stop", stop_spam))
    
    application.run_polling()

if __name__ == '__main__':
    main()