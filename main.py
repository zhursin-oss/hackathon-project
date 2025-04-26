import telebot
import requests
import logging

TELEGRAM_TOKEN = '7611949438:AAE425r384GRiDh6YJuiLbSAl6AmgeWo5Zw'
HUGGINGFACE_API_KEY = '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'

# Настройки моделей
MODEL_NAME = 'google/flan-t5-large'
TRANSLATION_MODELS = {
    'Kazakh': ('kk', 'en'),
    'Russian': ('ru', 'en'),
    'Turkish': ('tr', 'en'),
    'English': (None, None)  # Без перевода
}

# Инициализация бота
bot = telebot.TeleBot(TELEGRAM_TOKEN)
logging.basicConfig(level=logging.INFO)

# Храним выбранный язык и ожидание симптомов
user_language = {}
user_waiting_symptoms = {}

# Доступные языки
languages = {
    'Қазақша': 'Kazakh',
    'Русский': 'Russian',
    'English': 'English',
    'Türkçe': 'Turkish'
}

# Команда /start
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    for lang in languages.keys():
        markup.add(lang)
    bot.send_message(message.chat.id, "Тілді таңдаңыз / Выберите язык / Select a language / Bir dil seçin:", reply_markup=markup)

# Выбор языка
@bot.message_handler(func=lambda message: message.text in languages.keys())
def choose_language(message):
    lang = languages[message.text]
    user_language[message.chat.id] = lang
    user_waiting_symptoms[message.chat.id] = True

    greetings = {
        'Kazakh': "Сәлеметсіз бе! Мен сіздің медициналық көмекшіңіз МедиБотпын. Симптомдарыңызды жазыңыз.",
        'Russian': "Привет! Я твой медицинский помощник Медибот. Напишите свои симптомы.",
        'English': "Hello! I'm your medical assistant MediBot. Please describe your symptoms.",
        'Turkish': "Merhaba! Ben sizin tıbbi yardımcınız MediBot'um. Lütfen belirtilerinizi yazınız."
    }

    bot.send_message(message.chat.id, greetings[lang])

# Обработка симптомов
@bot.message_handler(func=lambda message: user_waiting_symptoms.get(message.chat.id, False))
def handle_symptoms(message):
    symptoms = message.text
    lang = user_language.get(message.chat.id, 'English')

    try:
        # Переводим симптомы на английский
        symptoms_in_english = translate_text(symptoms, TRANSLATION_MODELS[lang][0], 'en') if lang != 'English' else symptoms

        # Отправляем симптомы в Hugging Face
        diagnosis = ask_huggingface(symptoms_in_english)

        if diagnosis:
            # Перевод обратно на нужный язык
            final_diagnosis = translate_text(diagnosis, 'en', TRANSLATION_MODELS[lang][0]) if lang != 'English' else diagnosis
            bot.send_message(message.chat.id, final_diagnosis.strip())
        else:
            send_error_message(message.chat.id)
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        send_error_message(message.chat.id)

def send_error_message(chat_id):
    bot.send_message(chat_id, "Қате пайда болды, кейінірек қайталап көріңіз.\nПроизошла ошибка, попробуйте позже.\nAn error occurred, please try again later.\nBir hata oluştu, lütfen daha sonra tekrar deneyin.")

def ask_huggingface(symptoms_text):
    prompt = f"""Определи болезнь на основе симптомов: {symptoms_text}.
Кратко опиши (1 предложение).
Дай рекомендацию: домашнее лечение или обратиться в больницу."""

    headers = {
        "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "inputs": prompt,
        "parameters": {
            "temperature": 0.7,
            "max_new_tokens": 200
        }
    }
    response = requests.post(
        f"https://api-inference.huggingface.co/models/{MODEL_NAME}",
        headers=headers,
        json=payload
    )
    if response.status_code == 200:
        return response.json()[0]['generated_text']
    else:
        logging.error(f"HuggingFace API error: {response.status_code} {response.text}")
        return None

def translate_text(text, source_lang, target_lang):
    if not source_lang or not target_lang:
        return text

    model_id = f"Helsinki-NLP/opus-mt-{source_lang}-{target_lang}"

    headers = {
        "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {"inputs": text}
    response = requests.post(
        f"https://api-inference.huggingface.co/models/{model_id}",
        headers=headers,
        json=payload
    )

    if response.status_code == 200:
        translated_text = response.json()[0]['translation_text']
        return translated_text
    else:
        logging.error(f"Translation API error: {response.status_code} {response.text}")
        return text

# Запуск бота
if __name__ == "__main__":
    bot.polling(non_stop=True)