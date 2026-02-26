import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Включим логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота (ЗАМЕНИТЕ НА СВОЙ!)
TOKEN = '8499345141:AAE-F5VSbDy3ToCXul6cFAg9HN2u-nb0sCs'

# Класс для калькулятора
class Calculator:
    def __init__(self):
        self.expression = ""
        self.result = ""
        self.last_result = ""
    
    def add_symbol(self, symbol):
        if symbol == 'C':
            self.expression = ""
            self.result = ""
        elif symbol == '⌫':
            self.expression = self.expression[:-1]
        elif symbol == '=':
            self.calculate()
        elif symbol == 'ANS':
            if self.last_result:
                self.expression += str(self.last_result)
        else:
            self.expression += symbol
    
    def calculate(self):
        try:
            # Заменяем символы для eval
            expr = (self.expression
                   .replace('×', '*')
                   .replace('÷', '/')
                   .replace('²', '**2')
                   .replace('√', '**0.5'))
            
            # Безопасное вычисление
            result = eval(expr, {"__builtins__": {}}, {})
            self.result = str(result)
            self.last_result = result
        except Exception as e:
            self.result = "Ошибка"
    
    def get_display(self):
        if self.result:
            return f"{self.expression}\n= {self.result}"
        return self.expression if self.expression else "0"

# Хранилище калькуляторов для каждого пользователя
user_calculators = {}

def get_calculator(user_id):
    if user_id not in user_calculators:
        user_calculators[user_id] = Calculator()
    return user_calculators[user_id]

def create_calculator_keyboard():
    """Создает клавиатуру калькулятора с синими кнопками"""
    
    # Синий цвет для кнопок (через эмодзи и текст)
    keyboard = [
        [
            InlineKeyboardButton("🔵 C", callback_data="calc_C"),
            InlineKeyboardButton("🔵 ⌫", callback_data="calc_⌫"),
            InlineKeyboardButton("🔵 ÷", callback_data="calc_÷"),
            InlineKeyboardButton("🔵 ×", callback_data="calc_×")
        ],
        [
            InlineKeyboardButton("🔵 7", callback_data="calc_7"),
            InlineKeyboardButton("🔵 8", callback_data="calc_8"),
            InlineKeyboardButton("🔵 9", callback_data="calc_9"),
            InlineKeyboardButton("🔵 -", callback_data="calc_-")
        ],
        [
            InlineKeyboardButton("🔵 4", callback_data="calc_4"),
            InlineKeyboardButton("🔵 5", callback_data="calc_5"),
            InlineKeyboardButton("🔵 6", callback_data="calc_6"),
            InlineKeyboardButton("🔵 +", callback_data="calc_+")
        ],
        [
            InlineKeyboardButton("🔵 1", callback_data="calc_1"),
            InlineKeyboardButton("🔵 2", callback_data="calc_2"),
            InlineKeyboardButton("🔵 3", callback_data="calc_3"),
            InlineKeyboardButton("🔵 =", callback_data="calc_=")
        ],
        [
            InlineKeyboardButton("🔵 0", callback_data="calc_0"),
            InlineKeyboardButton("🔵 .", callback_data="calc_."),
            InlineKeyboardButton("🔵 ( )", callback_data="calc_()"),
            InlineKeyboardButton("🔵 ANS", callback_data="calc_ANS")
        ],
        [
            InlineKeyboardButton("🔵 x²", callback_data="calc_²"),
            InlineKeyboardButton("🔵 √", callback_data="calc_√"),
            InlineKeyboardButton("🔵 %", callback_data="calc_%"),
            InlineKeyboardButton("🔵 ±", callback_data="calc_±")
        ]
    ]
    
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение с баннером как обычный текст"""
    
    banner = """⠀⣶⣶⡆⢠⣶⣶⠀⣶⡶⠶⠶⠀⣴⣶⠶⠶⠀⣶⡶⠶⠶⠆⠶⠶⣶⣶⠆⠰⣶⡀⣠⡶⠂
⠀⣿⡟⣷⣼⢿⣿⠀⣿⡷⠶⠶⠀⣿⣷⠶⠶⠀⣿⡷⠶⠶⠀⠀⣴⡿⠃⠀⠀⠙⣿⡟⠁⠀
⠀⠿⠇⠻⠏⠸⠿⠀⠿⠷⠶⠶⠀⠿⠇⠀⠀⠀⠿⠷⠶⠶⠆⠾⠿⠷⠶⠆⠀⠀⠿⠇⠀⠀"""
    
    welcome_text = f"{banner}\n\n🧮 ДОБРО ПОЖАЛОВАТЬ В КАЛЬКУЛЯТОР MEFEZY!\n\nНажмите /calc чтобы открыть калькулятор"
    
    await update.message.reply_text(welcome_text)

async def calc_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Открывает калькулятор"""
    
    user_id = update.effective_user.id
    calculator = get_calculator(user_id)
    
    display_text = f"🧮 Калькулятор Mefezy\n{calculator.get_display()}"
    
    await update.message.reply_text(
        display_text,
        reply_markup=create_calculator_keyboard()
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатия кнопок"""
    
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    calculator = get_calculator(user_id)
    
    # Получаем нажатую кнопку
    callback_data = query.data
    if callback_data.startswith("calc_"):
        symbol = callback_data[5:]  # Убираем префикс "calc_"
        
        # Обработка специальных функций
        if symbol == "()":
            calculator.add_symbol("(")
            calculator.add_symbol(")")
        elif symbol == "²":
            calculator.add_symbol("²")
        elif symbol == "√":
            calculator.add_symbol("√")
        elif symbol == "%":
            current = calculator.expression
            if current and current[-1].isdigit():
                calculator.add_symbol("/100")
        elif symbol == "±":
            if calculator.expression and calculator.expression[0] == '-':
                calculator.expression = calculator.expression[1:]
            else:
                calculator.expression = '-' + calculator.expression
        elif symbol == "ANS":
            calculator.add_symbol("ANS")
        else:
            calculator.add_symbol(symbol)
        
        # Обновляем дисплей
        display_text = f"🧮 Калькулятор Mefezy\n{calculator.get_display()}"
        
        await query.edit_message_text(
            display_text,
            reply_markup=create_calculator_keyboard()
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает справку"""
    
    help_text = """
📚 ПОМОЩЬ ПО КАЛЬКУЛЯТОРУ

Команды:
/start - Показать баннер
/calc - Открыть калькулятор
/help - Эта справка
/clear - Очистить калькулятор

Функции кнопок:
• C - Очистить все
• ⌫ - Удалить последний символ
• ( ) - Скобки
• ANS - Вставить предыдущий результат
• x² - Возведение в квадрат
• √ - Квадратный корень
• % - Процент
• ± - Смена знака

Примеры:
2 + 2 × 2 = 6
(2 + 2) × 2 = 8
√9 = 3
5² = 25
    """
    
    await update.message.reply_text(help_text)

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Очищает калькулятор"""
    
    user_id = update.effective_user.id
    if user_id in user_calculators:
        del user_calculators[user_id]
    
    await update.message.reply_text("✅ Калькулятор очищен! Используйте /calc чтобы начать заново.")

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отвечает на неизвестные команды"""
    
    await update.message.reply_text("❌ Неизвестная команда. Используйте /help для списка команд.")

def main() -> None:
    """Запускает бота"""
    
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("calc", calc_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CallbackQueryHandler(button_callback, pattern="^calc_"))
    
    # Обработчик неизвестных команд
    application.add_handler(CommandHandler("unknown", unknown_command))
    
    # Запускаем бота
    print("🤖 Бот-калькулятор Mefezy запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
