import logging
import requests
from langdetect import detect
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import os

TELEGRAM_TOKEN = "7611949438:AAE425r384GRiDh6YJuiLbSAl6AmgeWo5Zw"
HUGGINGFACE_API_KEY = "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"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Функция для определения языка входящего текста
def detect_language(text: str) -> str:
    try:
        return detect(text)  # Возвращает код языка, например, "ru", "en", "tr", "kk" и т.п.
    except Exception as e:
        logger.error(f"Ошибка определения языка: {e}")
        return "en"  # По умолчанию английский

# Функция перевода через Hugging Face (с использованием модели Helsinki‑NLP)
def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    # Для перевода с русского на английский используем модель opus-mt-ru-en,
    # для турецкого – opus-mt-tr-en и т.д.
    # Если source_lang == target_lang – возвращаем текст без изменений.
    if source_lang.lower() == target_lang.lower():
        return text

    # Составляем имя модели; пока реализуем только для ru, tr и en.
    model_map = {
        ("ru", "en"): "Helsinki-NLP/opus-mt-ru-en",
        ("en", "ru"): "Helsinki-NLP/opus-mt-en-ru",
        ("tr", "en"): "Helsinki-NLP/opus-mt-tr-en",
        ("en", "tr"): "Helsinki-NLP/opus-mt-en-tr",
        # Для казахского можно попробовать, но модели типа opus-mt-kk-en могут отсутствовать.
    }
    key = (source_lang.lower(), target_lang.lower())
    if key not in model_map:
        # Если модели для данной пары нет, возвращаем оригинальный текст.
        return text

    model_name = model_map[key]
    url = f"https://api-inference.huggingface.co/models/{model_name}"
    headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
    payload = {"inputs": text}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()
        translation = result[0].get("translation_text", None)
        if translation:
            return translation.strip()
        else:
            logger.error(f"Ошибка перевода, ответ: {result}")
            return text
    except Exception as e:
        logger.error(f"Translation API error: {e}")
        # Возвращаем сообщение об ошибке (как запрос от пользователя)
        return "Переводчик временно недоступен, пожалуйста, повторите попытку позже."

# Функция анализа симптомов (запрос к Hugging Face модели)
def analyze_symptoms(symptoms_english: str) -> str:
    prompt = (
        f"Based on the following symptoms: {symptoms_english}\n"
        f"Identify the illness in one sentence and then provide a recommendation: either 'home treatment' or 'go to the hospital'."
    )
    url = "https://api-inference.huggingface.co/models/google/flan-t5-large"
    headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}", "Content-Type": "application/json"}
    payload = {"inputs": prompt, "parameters": {"temperature": 0.7, "max_new_tokens": 150}}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        result = response.json()
        diagnosis = result[0].get("generated_text", "").strip()
        return diagnosis
    except Exception as e:
        logger.error(f"HuggingFace API error in analyze_symptoms: {e}")
        return None

# Функция поиска ближайших больниц через Overpass API (OpenStreetMap)
def get_nearby_hospitals(lat: float, lon: float) -> list:
    query = f"""
    [out:json];
    (
      node["amenity"="hospital"](around:5000,{lat},{lon});
      way["amenity"="hospital"](around:5000,{lat},{lon});
      relation["amenity"="hospital"](around:5000,{lat},{lon});
    );
    out center;
    """
    url = "http://overpass-api.de/api/interpreter"
    try:
        response = requests.post(url, data={"data": query}, timeout=15)
        response.raise_for_status()
        data = response.json()
        hospitals = []
        for element in data.get("elements", []):
            # Попытка извлечь имя
            name = element.get("tags", {}).get("name", "Без названия")
            hospitals.append(name)
        return hospitals
    except Exception as e:
        logger.error(f"Overpass API error: {e}")
        return None

# Глобальная переменная, чтобы отметить, что пользователю надо запросить геолокацию
# Если диагноз содержит ключевое слово "hospital" (в английском ответе), считаем ситуацию серьёзной.
# Для простоты будем искать подстроку "hospital" в diagnosis (можно расширить).
pending_hospital_request = {}

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Привет! Напишите ваши симптомы. Я помогу определить, нужно ли обращаться в больницу.")

# Обработчик текстовых сообщений (симптомы)
async def handle_symptoms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_text = update.message.text
    chat_id = update.message.chat_id

    # Определяем язык исходного текста
    source_lang = detect_language(user_text)
    # Если не английский, переводим симптомы на английский
    if source_lang != "en":
        symptoms_english = translate_text(user_text, source_lang, "en")
    else:
        symptoms_english = user_text

    if not symptoms_english:
        await update.message.reply_text("Не удалось обработать ваши симптомы. Попробуйте еще раз.")
        return

    # Анализируем симптомы (на английском)
    diagnosis_english = analyze_symptoms(symptoms_english)
    if diagnosis_english is None:
        await update.message.reply_text("Извините, я не смог определить заболевание. Попробуйте позже.")
        return

    # Теперь, если исходный язык не английский, переводим диагноз обратно
    if source_lang != "en":
        diagnosis = translate_text(diagnosis_english, "en", source_lang)
    else:
        diagnosis = diagnosis_english

    await update.message.reply_text(f"Диагноз: {diagnosis}")

    # Если в диагнозе содержится слово "hospital" (или аналог) - считаем, что нужно обращаться в больницу
    if "hospital" in diagnosis_english.lower() or "go to the hospital" in diagnosis_english.lower():
        pending_hospital_request[chat_id] = True
        # Спрашиваем пользователя отправить геолокацию через кнопку
        location_button = KeyboardButton("Отправить геолокацию", request_location=True)
        reply_markup = ReplyKeyboardMarkup([[location_button]], resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("Обнаружена серьёзная ситуация. Пожалуйста, отправьте свою геолокацию для поиска ближайших больниц.", reply_markup=reply_markup)
    else:
        pending_hospital_request[chat_id] = False

# Обработчик геолокации
async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    if not pending_hospital_request.get(chat_id, False):
        await update.message.reply_text("Спасибо за геолокацию.")
        return

    loc = update.message.location
    lat, lon = loc.latitude, loc.longitude
    hospitals = get_nearby_hospitals(lat, lon)
    if hospitals:
        hospitals_list = "\n".join(hospitals[:5])  # выведем 5 ближайших
        await update.message.reply_text(f"Ближайшие больницы:\n{hospitals_list}")
    else:
        await update.message.reply_text("Извините, не удалось найти ближайшие больницы.")
    pending_hospital_request[chat_id] = False

# Основной запуск
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_symptoms))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))

    app.run_polling()

if __name__ == "__main__":
    main()