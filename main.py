import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
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

async def set_bot_commands(application: Application) -> None:
    """Устанавливает команды бота в меню"""
    
    commands = [
        BotCommand("start", "Показать приветствие с баннером"),
        BotCommand("calc", "Открыть калькулятор"),
        BotCommand("help", "Показать справку"),
        BotCommand("clear", "Очистить калькулятор"),
        BotCommand("photo", "Показать фото калькулятора"),
        BotCommand("menu", "Показать меню")
    ]
    
    await application.bot.set_my_commands(commands)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение с баннером как обычный текст"""
    
    banner = """⠀⣶⣶⡆⢠⣶⣶⠀⣶⡶⠶⠶⠀⣴⣶⠶⠶⠀⣶⡶⠶⠶⠆⠶⠶⣶⣶⠆⠰⣶⡀⣠⡶⠂
⠀⣿⡟⣷⣼⢿⣿⠀⣿⡷⠶⠶⠀⣿⣷⠶⠶⠀⣿⡷⠶⠶⠀⠀⣴⡿⠃⠀⠀⠙⣿⡟⠁⠀
⠀⠿⠇⠻⠏⠸⠿⠀⠿⠷⠶⠶⠀⠿⠇⠀⠀⠀⠿⠷⠶⠶⠆⠾⠿⠷⠶⠆⠀⠀⠿⠇⠀⠀"""
    
    # Кнопки меню
    keyboard = [
        [
            InlineKeyboardButton("🧮 Открыть калькулятор", callback_data="menu_calc"),
            InlineKeyboardButton("📖 Помощь", callback_data="menu_help")
        ],
        [
            InlineKeyboardButton("📸 Показать фото", callback_data="menu_photo"),
            InlineKeyboardButton("❓ О боте", callback_data="menu_about")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"{banner}\n\n🧮 ДОБРО ПОЖАЛОВАТЬ В КАЛЬКУЛЯТОР MEFEZY!\n\nВыберите действие:"
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает главное меню"""
    
    keyboard = [
        [
            InlineKeyboardButton("🧮 Калькулятор", callback_data="menu_calc"),
            InlineKeyboardButton("📖 Помощь", callback_data="menu_help")
        ],
        [
            InlineKeyboardButton("📸 Фото", callback_data="menu_photo"),
            InlineKeyboardButton("ℹ️ Инфо", callback_data="menu_info")
        ],
        [
            InlineKeyboardButton("🔄 Очистить", callback_data="menu_clear"),
            InlineKeyboardButton("🌟 Оценить", callback_data="menu_rate")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📱 ГЛАВНОЕ МЕНЮ\n\nВыберите нужный раздел:",
        reply_markup=reply_markup
    )

async def photo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет фото калькулятора"""
    
    photo_url = "https://ibb.co/fdC3dL3X"  # Замените на реальную ссылку
    
    caption = "🧮 Калькулятор Mefezy\n\nНажмите /calc чтобы начать вычисления!"
    
    keyboard = [
        [
            InlineKeyboardButton("📱 Открыть калькулятор", callback_data="menu_calc"),
            InlineKeyboardButton("🔙 Назад в меню", callback_data="menu_back")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await update.message.reply_photo(
            photo=photo_url,
            caption=caption,
            reply_markup=reply_markup
        )
    except:
        # Если фото не загружается, отправляем текст
        await update.message.reply_text(
            "📸 Фото временно недоступно.\n\nИспользуйте /calc для открытия калькулятора.",
            reply_markup=reply_markup
        )

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатия кнопок меню"""
    
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "menu_calc":
        user_id = update.effective_user.id
        calculator = get_calculator(user_id)
        display_text = f"🧮 Калькулятор Mefezy\n{calculator.get_display()}"
        await query.edit_message_text(
            display_text,
            reply_markup=create_calculator_keyboard()
        )
    
    elif data == "menu_help":
        help_text = """
📚 ПОМОЩЬ ПО КАЛЬКУЛЯТОРУ

Команды:
/start - Показать баннер
/calc - Открыть калькулятор
/help - Эта справка
/clear - Очистить калькулятор
/photo - Показать фото
/menu - Открыть меню

Функции кнопок:
• C - Очистить все
• ⌫ - Удалить последний символ
• ( ) - Скобки
• ANS - Вставить предыдущий результат
• x² - Возведение в квадрат
• √ - Квадратный корень
• % - Процент
• ± - Смена знака
        """
        
        keyboard = [[InlineKeyboardButton("🔙 Назад в меню", callback_data="menu_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(help_text, reply_markup=reply_markup)
    
    elif data == "menu_photo":
        photo_url = "https://ibb.co/fdC3dL3X"  # Замените на реальную ссылку
        caption = "🧮 Калькулятор Mefezy"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад в меню", callback_data="menu_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.message.reply_photo(
                photo=photo_url,
                caption=caption,
                reply_markup=reply_markup
            )
            await query.delete_message()
        except:
            await query.edit_message_text(
                "📸 Фото временно недоступно",
                reply_markup=reply_markup
            )
    
    elif data == "menu_about":
        about_text = """
ℹ️ О КАЛЬКУЛЯТОРЕ MEFEZY

Версия: 1.0
Разработчик: Mefezy
Описание: Простой и удобный калькулятор с синими кнопками

Особенности:
• Интуитивный интерфейс
• Поддержка скобок
• Память результатов (ANS)
• Математические функции

Используйте /calc для начала работы!
        """
        
        keyboard = [[InlineKeyboardButton("🔙 Назад в меню", callback_data="menu_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(about_text, reply_markup=reply_markup)
    
    elif data == "menu_clear":
        user_id = update.effective_user.id
        if user_id in user_calculators:
            del user_calculators[user_id]
        
        keyboard = [
            [
                InlineKeyboardButton("🧮 Калькулятор", callback_data="menu_calc"),
                InlineKeyboardButton("🔙 Меню", callback_data="menu_back")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "✅ Калькулятор очищен!\n\nЧто дальше?",
            reply_markup=reply_markup
        )
    
    elif data == "menu_rate":
        rate_text = "🌟 Оцените бота:\n\n1 - Плохо\n2 - Средне\n3 - Хорошо\n4 - Отлично\n5 - Прекрасно!"
        
        keyboard = [
            [
                InlineKeyboardButton("1", callback_data="rate_1"),
                InlineKeyboardButton("2", callback_data="rate_2"),
                InlineKeyboardButton("3", callback_data="rate_3"),
                InlineKeyboardButton("4", callback_data="rate_4"),
                InlineKeyboardButton("5", callback_data="rate_5")
            ],
            [InlineKeyboardButton("🔙 Назад", callback_data="menu_back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(rate_text, reply_markup=reply_markup)
    
    elif data.startswith("rate_"):
        rating = data[5:]
        await query.edit_message_text(
            f"✅ Спасибо за оценку {rating}/5!\n\nМы стараемся стать лучше!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 В меню", callback_data="menu_back")
            ]])
        )
    
    elif data == "menu_back":
        keyboard = [
            [
                InlineKeyboardButton("🧮 Калькулятор", callback_data="menu_calc"),
                InlineKeyboardButton("📖 Помощь", callback_data="menu_help")
            ],
            [
                InlineKeyboardButton("📸 Фото", callback_data="menu_photo"),
                InlineKeyboardButton("ℹ️ Инфо", callback_data="menu_info")
            ],
            [
                InlineKeyboardButton("🔄 Очистить", callback_data="menu_clear"),
                InlineKeyboardButton("🌟 Оценить", callback_data="menu_rate")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📱 ГЛАВНОЕ МЕНЮ\n\nВыберите нужный раздел:",
            reply_markup=reply_markup
        )
    
    elif data == "menu_info":
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="menu_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "ℹ️ Информация о боте:\n\nВерсия: 1.0\nСоздатель: Mefezy\nБот-калькулятор с синими кнопками",
            reply_markup=reply_markup
        )

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
    """Обрабатывает нажатия кнопок калькулятора"""
    
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
/photo - Показать фото
/menu - Открыть меню

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
    application.add_handler(CommandHandler("photo", photo_command))
    application.add_handler(CommandHandler("menu", menu_command))
    
    # Обработчики callback-запросов
    application.add_handler(CallbackQueryHandler(menu_callback, pattern="^menu_"))
    application.add_handler(CallbackQueryHandler(button_callback, pattern="^calc_"))
    application.add_handler(CallbackQueryHandler(menu_callback, pattern="^rate_"))
    
    # Обработчик неизвестных команд
    application.add_handler(CommandHandler("unknown", unknown_command))
    
    # Устанавливаем команды в меню после запуска
    application.post_init = set_bot_commands
    
    # Запускаем бота
    print("🤖 Бот-калькулятор Mefezy запущен...")
    print("✅ Команды добавлены в меню!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
