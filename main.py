import telebot
import requests

API_TOKEN = '7611949438:AAE425r384GRiDh6YJuiLbSAl6AmgeWo5Zw'
HUGGINGFACE_API_KEY = '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'

bot = telebot.TeleBot(API_TOKEN)

user_lang = {}

languages = {
    'kk': 'Қазақша',
    'ru': 'Русский',
    'en': 'English',
    'tr': 'Türkçe'
}

@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    for code, lang in languages.items():
        markup.add(telebot.types.KeyboardButton(lang))
    bot.send_message(message.chat.id, "Менің атым MediBot. Тілді таңдаңыз / Выберите язык / Choose language / Dil seçin:", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text in languages.values())
def set_language(message):
    for code, lang in languages.items():
        if message.text == lang:
            user_lang[message.chat.id] = code
            greetings = {
                'kk': "Симптомдарыңызды жазыңыз.",
                'ru': "Напишите ваши симптомы.",
                'en': "Please type your symptoms.",
                'tr': "Lütfen belirtilerinizi yazınız."
            }
            bot.send_message(message.chat.id, greetings[code])
            break

@bot.message_handler(content_types=['text'])
def handle_symptoms(message):
    lang = user_lang.get(message.chat.id, 'en')
    text = message.text

    # Шаг 1: Перевести симптомы на английский, если они не на английском
    if lang != 'en':
        text = translate_text(text, source_lang=lang, target_lang='en')

    # Шаг 2: Отправить симптомы на Hugging Face
    diagnosis = ask_huggingface(text)

    # Шаг 3: Перевести диагноз обратно на язык пользователя
    if lang != 'en':
        diagnosis = translate_text(diagnosis, source_lang='en', target_lang=lang)

    bot.send_message(message.chat.id, diagnosis)

    # Шаг 4: Если есть тяжелые симптомы, попросить геолокацию
    if any(word in message.text.lower() for word in ['ауыр', 'болит', 'pain', 'ağrı']):
        send_location_request(message.chat.id, lang)

def ask_huggingface(symptoms):
    headers = {
        "Authorization": f"Bearer {HUGGINGFACE_API_KEY}"
    }
    payload = {
        "inputs": f"The patient has the following symptoms: {symptoms}. What could be the possible diagnosis?"
    }
    response = requests.post("https://api-inference.huggingface.co/models/google/flan-t5-base", headers=headers, json=payload)
    if response.status_code == 200:
        result = response.json()
        if isinstance(result, list) and 'generated_text' in result[0]:
            return result[0]['generated_text']
        else:
            return "Не удалось получить диагноз."
    else:
        return "Ошибка сервера при диагностике."

def translate_text(text, source_lang, target_lang):
    # Используем Hugging Face для перевода текста
    model_map = {
        ('kk', 'en'): 'Helsinki-NLP/opus-mt-kk-en',
        ('ru', 'en'): 'Helsinki-NLP/opus-mt-ru-en',
        ('tr', 'en'): 'Helsinki-NLP/opus-mt-tr-en',
        ('en', 'kk'): 'Helsinki-NLP/opus-mt-en-kk',
        ('en', 'ru'): 'Helsinki-NLP/opus-mt-en-ru',
        ('en', 'tr'): 'Helsinki-NLP/opus-mt-en-tr'
    }
    model = model_map.get((source_lang, target_lang))
    if not model:
        return text  # Если нет нужной модели, возвращаем как есть

    headers = {
        "Authorization": f"Bearer {HUGGINGFACE_API_KEY}"
    }
    payload = {
        "inputs": text
    }
    response = requests.post(f"https://api-inference.huggingface.co/models/{model}", headers=headers, json=payload)
    if response.status_code == 200:
        result = response.json()
        if isinstance(result, list) and 'translation_text' in result[0]:
            return result[0]['translation_text']
    return text

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

@bot.message_handler(content_types=['location'])
def handle_location(message):
    lat = message.location.latitude
    lon = message.location.longitude
    bot.send_message(message.chat.id, f"Міне, сізге жақын ауруханалар:\nhttps://www.google.com/maps/search/hospital/@{lat},{lon},14z")

bot.polling(non_stop=True)