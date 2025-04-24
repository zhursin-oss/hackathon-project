import telebot

TOKEN = "7611949438:AAE425r384GRiDh6YJuiLbSAl6AmgeWo5Zw"
bot = telebot.TeleBot(TOKEN)

# Храним состояние пользователя
user_state = {}
user_language = {}

# Языки
languages = {
    "kz": "Қазақ тілі",
    "ru": "Русский",
    "en": "English",
    "tr": "Türkçe"
}

# Симптом -> Болезнь
symptom_to_disease = {
    "голова": ("Головная боль", False),
    "кашель": ("Простуда", False),
    "температура": ("Грипп", False),
    "боль в груди": ("Проблемы с сердцем", True),
    "живот": ("Отравление", False)
}

@bot.message_handler(commands=['start'])
def start_message(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for lang in languages.values():
        markup.add(lang)
    bot.send_message(message.chat.id, "Сәлем! Мен — сенің медициналық көмекшің MediBot.\nАлдымен тіл таңдаңыз:", reply_markup=markup)
    user_state[message.chat.id] = "choose_language"

@bot.message_handler(func=lambda msg: True)
def handle_message(message):
    chat_id = message.chat.id
    text = message.text.strip().lower()

    # Шаг 1: выбор языка
    if user_state.get(chat_id) == "choose_language":
        for key, value in languages.items():
            if value.lower() in text:
                user_language[chat_id] = key
                user_state[chat_id] = "ask_symptom"
                bot.send_message(chat_id, "Симптомыңызды жазыңыз / Напишите ваш симптом / Write your symptom / Semptomunuzu yazın:")
                return
        bot.send_message(chat_id, "Тілді дұрыс таңдаңыз.")

    # Шаг 2: ввод симптома
    elif user_state.get(chat_id) == "ask_symptom":
        response = check_symptom(text)
        bot.send_message(chat_id, response)

def check_symptom(symptom_text):
    for key in symptom_to_disease:
        if key in symptom_text:
            disease, is_serious = symptom_to_disease[key]
            if is_serious:
                return f"Бұл қауіпті болуы мүмкін: {disease}. Жақын ауруханаға барыңыз!"
            else:
                return f"Сізде {disease}. Үйде емделуге болады. Көп су ішіңіз, демалыңыз."
    return "Кешіріңіз, бұл симптом бойынша менде мәлімет жоқ."

bot.polling()