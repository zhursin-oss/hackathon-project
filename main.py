import telebot
import requests

API_TOKEN = '7611949438:AAE425r384GRiDh6YJuiLbSAl6AmgeWo5Zw'
HUGGINGFACE_API_KEY = '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'

# Инициализация бота
bot = telebot.TeleBot(API_TOKEN)

# Храним язык пользователя
user_lang = {}

# Языки
languages = {
    'kk': 'Қазақша',
    'ru': 'Русский',
    'en': 'English',
    'tr': 'Türkçe'
}


# Стартовое сообщение
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    for code, lang in languages.items():
        markup.add(telebot.types.KeyboardButton(lang))
    bot.send_message(message.chat.id,
                     "Менің атым MediBot. Тілді таңдаңыз / Выберите язык / Choose language / Dil seçin:",
                     reply_markup=markup)


# Установка языка
@bot.message_handler(func=lambda msg: msg.text in languages.values())
def set_language(message):
    for code, lang in languages.items():
        if message.text == lang:
            user_lang[message.chat.id] = code
            greetings = {
                'kk': "Симптомдарыңызды жазыңыз",
                'ru': "Напишите ваши симптомы",
                'en': "Please type your symptoms",
                'tr': "Lütfen belirtilerinizi yazınız"
            }
            bot.send_message(message.chat.id, greetings[code])
            break


# Обработка симптомов
@bot.message_handler(content_types=['text'])
def handle_symptoms(message):
    lang = user_lang.get(message.chat.id, 'en')
    symptoms = message.text

    # Отправляем запрос на Hugging Face для получения диагноза
    response = ask_huggingface(symptoms)

    # Отправляем ответ пользователю
    bot.send_message(message.chat.id, response)

    # Если симптомы указывают на серьезное состояние, запросить геолокацию
    if any(word in symptoms.lower() for word in ['ауыр', 'болит', 'pain', 'ağrı']):
        send_location_request(message.chat.id, lang)


# Запрос к Hugging Face для получения диагноза
def ask_huggingface(symptoms):
    headers = {
        "Authorization": f"Bearer {HUGGINGFACE_API_KEY}"
    }
    payload = {
        "inputs": f"Given the symptoms: {symptoms}, what is the most likely diagnosis?"
    }
    response = requests.post("https://api-inference.huggingface.co/models/google/flan-t5-base", headers=headers,
                             json=payload)
    if response.status_code == 200:
        result = response.json()
        if isinstance(result, list) and 'generated_text' in result[0]:
            return result[0]['generated_text']
        else:
            return "Не удалось получить диагноз."
    else:
        return "Ошибка сервера при диагностике."


# Обработка геолокации
def send_location_request(chat_id, lang):
    text = {
        'kk': "Орналасқан жеріңізді жіберіңіз, жақын аурухананы көрсетемін.",
        'ru': "Отправьте ваше местоположение, покажу ближайшую больницу.",
        'en': "Send your location to show the nearest hospital.",
        'tr': "Konumunuzu gönderin, en yakın hastaneyi göstereyim."
    }
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    button = telebot.types.KeyboardButton(text[lang], request_location=True)
    markup.add(button)
    bot.send_message(chat_id, text[lang], reply_markup=markup)


# Обработка геолокации
@bot.message_handler(content_types=['location'])
def handle_location(message):
    lat = message.location.latitude
    lon = message.location.longitude
    bot.send_message(message.chat.id,
                     f"Міне, сізге жақын ауруханалар:\nhttps://www.google.com/maps/search/hospital/@{lat},{lon},14z")


# Запуск бота
bot.polling(non_stop=True)