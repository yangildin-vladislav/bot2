import os
import io
import json
import zipfile
import urllib.request
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)
from PIL import Image, ImageDraw, ImageFont

BOT_TOKEN = "8463686645:AAEdU7o2fX_UtaJFh7OhAJvI9Jt2pBSiAig"
TEMPLATE_FILE = "template.json"
COUNTER_FILE  = "counter.json"

(WAIT_IMAGE, WAIT_FONT, WAIT_SIZE, WAIT_TEXT1, WAIT_TEXT2) = range(5)

FONT_URL  = "https://github.com/google/fonts/raw/main/ofl/opensans/OpenSans%5Bwdth%2Cwght%5D.ttf"
FONT_PATH = "fonts/OpenSans.ttf"

FONT_MENU = (
    "🎨 Выбери стиль — отправь цифру:\n\n"
    "1 — Обычный\n"
    "2 — Жирный (многослойная тень)\n"
    "3 — Неон (голубое свечение)\n"
    "4 — Тень снизу\n"
    "5 — Белый с чёрной обводкой"
)

SIZE_MENU = (
    "📏 Отправь размер шрифта числом:\n\n"
    "60  — мелкий\n"
    "100 — средний\n"
    "150 — крупный\n"
    "200 — очень крупный\n\n"
    "Напиши любое число от 20 до 400"
)

# ─── СЧЁТЧИК ─────────────────────────────
def get_next_counter():
    counter = 1
    if os.path.exists(COUNTER_FILE):
        with open(COUNTER_FILE, "r") as f:
            counter = json.load(f).get("count", 1)
    with open(COUNTER_FILE, "w") as f:
        json.dump({"count": counter + 1}, f)
    return counter

# ─── ШРИФТ ───────────────────────────────
def ensure_font():
    os.makedirs("fonts", exist_ok=True)
    if not os.path.exists(FONT_PATH):
        print("⬇️ Скачиваю шрифт...")
        urllib.request.urlretrieve(FONT_URL, FONT_PATH)
        print("✅ Шрифт скачан!")

def get_font(size):
    try:
        if os.path.exists(FONT_PATH):
            return ImageFont.truetype(FONT_PATH, size)
        for fb in [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]:
            if os.path.exists(fb):
                return ImageFont.truetype(fb, size)
    except Exception:
        pass
    return ImageFont.load_default()

# ─── ШАБЛОН ──────────────────────────────
def load_template():
    if os.path.exists(TEMPLATE_FILE):
        with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_template(data):
    with open(TEMPLATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ─── РЕНДЕР ──────────────────────────────
def wrap_text(draw, text, font, max_width):
    result = []
    for paragraph in text.split("\n"):
        if paragraph.strip() == "":
            result.append("")
            continue
        words = paragraph.split()
        current = ""
        for word in words:
            test = (current + " " + word).strip()
            if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
                current = test
            else:
                if current:
                    result.append(current)
                current = word
        if current:
            result.append(current)
    return result or [""]

def render_image(image_bytes, text, style, font_size):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    draw = ImageDraw.Draw(img)
    w, h = img.size
    font = get_font(font_size)
    lines = wrap_text(draw, text, font, int(w * 0.88))
    line_height = int(font_size * 1.4)
    total_h = line_height * len(lines)
    y_start = (h - total_h) // 2

    for i, line in enumerate(lines):
        y = y_start + i * line_height
        if line == "":
            continue
        bbox = draw.textbbox((0, 0), line, font=font)
        x = (w - (bbox[2] - bbox[0])) // 2

        if style == "1":
            s = max(3, font_size // 15)
            draw.text((x+s, y+s), line, font=font, fill=(0, 0, 0, 180))
            draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        elif style == "2":
            for d in range(4, 0, -1):
                draw.text((x+d, y+d), line, font=font, fill=(0, 0, 0, 120))
            draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        elif style == "3":
            for spread in [12, 8, 4]:
                for dx in range(-spread, spread+1, 2):
                    for dy in range(-spread, spread+1, 2):
                        draw.text((x+dx, y+dy), line, font=font, fill=(0, 200, 255, 60))
            draw.text((x, y), line, font=font, fill=(200, 255, 255, 255))
        elif style == "4":
            s = max(4, font_size // 10)
            draw.text((x+s, y+s), line, font=font, fill=(0, 0, 0, 200))
            draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        elif style == "5":
            s = max(3, font_size // 20)
            for dx in range(-s, s+1):
                for dy in range(-s, s+1):
                    if abs(dx) == s or abs(dy) == s:
                        draw.text((x+dx, y+dy), line, font=font, fill=(0, 0, 0, 255))
            draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))

    out = io.BytesIO()
    img.convert("RGB").save(out, format="JPEG", quality=95)
    return out.getvalue()

# ─── ОБРАБОТКА ОДНОЙ КАРТИНКИ ────────────
async def process_one(update, image_bytes, settings):
    n = get_next_counter()
    style     = settings["style"]
    font_size = int(settings["font_size"])
    text1     = settings["text1"]
    text2     = settings["text2"]
    try:
        img1 = render_image(image_bytes, text1, style, font_size)
        img2 = render_image(image_bytes, text2, style, font_size)
        await update.message.reply_document(io.BytesIO(img1), filename=f"{n} - левое.jpg",  caption=f"🖼 {n} | {text1}")
        await update.message.reply_document(io.BytesIO(img2), filename=f"{n} - правое.jpg", caption=f"🎵 {n} | текст трека")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка на фото {n}: {e}")

async def process_batch_to_zip(update, names, zf_in, settings):
    """Обрабатывает все фото и возвращает zip в памяти."""
    zip_buffer = io.BytesIO()
    total = len(names)
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf_out:
        for i, name in enumerate(names, 1):
            img_bytes = zf_in.read(name)
            n = get_next_counter()
            style     = settings["style"]
            font_size = int(settings["font_size"])
            text1     = settings["text1"]
            text2     = settings["text2"]
            try:
                img1 = render_image(img_bytes, text1, style, font_size)
                img2 = render_image(img_bytes, text2, style, font_size)
                zf_out.writestr(f"{n} - левое.jpg",  img1)
                zf_out.writestr(f"{n} - правое.jpg", img2)
            except Exception as e:
                await update.message.reply_text(f"❌ Ошибка на фото {n}: {e}")
            if i % 10 == 0:
                await update.message.reply_text(f"⏳ Обработано {i}/{total}...")
    zip_buffer.seek(0)
    return zip_buffer

# ─── ХЕНДЛЕРЫ ────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tmpl = load_template()
    style_names = {"1":"Обычный","2":"Жирный","3":"Неон","4":"Тень","5":"Обводка"}
    if tmpl:
        await update.message.reply_text(
            "👋 Привет!\n\n"
            f"📋 Активный шаблон:\n"
            f"  • Стиль: {style_names.get(tmpl.get('style','1'))}\n"
            f"  • Размер: {tmpl.get('font_size')}\n"
            f"  • Текст 1: {tmpl.get('text1')}\n"
            f"  • Текст 2: {tmpl.get('text2')}\n\n"
            "📸 Кидай одну картинку или zip с несколькими!\n"
            "/newtemplate — изменить шаблон"
        )
    else:
        await update.message.reply_text(
            "👋 Привет!\n\n"
            "📸 Кидай картинку чтобы начать!\n"
            "Или zip-архив с несколькими фотками сразу 🗜"
        )
    return WAIT_IMAGE

async def new_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if os.path.exists(TEMPLATE_FILE):
        os.remove(TEMPLATE_FILE)
    context.user_data.clear()
    await update.message.reply_text("🗑 Шаблон сброшен!\n\n📸 Кидай картинку чтобы настроить заново")
    return WAIT_IMAGE

async def receive_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Одна картинка."""
    if update.message.photo:
        file = await update.message.photo[-1].get_file()
    elif update.message.document and update.message.document.mime_type.startswith("image/"):
        file = await update.message.document.get_file()
    else:
        await update.message.reply_text("Отправь картинку или zip-архив!")
        return WAIT_IMAGE

    context.user_data["image"] = bytes(await file.download_as_bytearray())

    tmpl = load_template()
    if tmpl:
        await update.message.reply_text("⏳ Применяю шаблон...")
        await process_one(update, context.user_data["image"], tmpl)
        context.user_data.clear()
        return WAIT_IMAGE

    await update.message.reply_text(FONT_MENU)
    return WAIT_FONT

async def receive_zip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ZIP-архив с кучей картинок."""
    doc = update.message.document
    if not doc or not (doc.file_name.endswith(".zip") or doc.mime_type == "application/zip"):
        return  # не наш файл

    tmpl = load_template()
    if not tmpl:
        await update.message.reply_text(
            "⚠️ Сначала настрой шаблон!\n\nОтправь одну картинку чтобы задать шрифт и тексты."
        )
        return WAIT_IMAGE

    await update.message.reply_text("📦 Получил архив, начинаю обработку...")

    file = await doc.get_file()
    zip_bytes = bytes(await file.download_as_bytearray())

    IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        # Только картинки, сортируем по имени
        names = sorted([
            n for n in zf.namelist()
            if any(n.lower().endswith(ext) for ext in IMAGE_EXTS)
            and not n.startswith("__MACOSX")
        ])

        if not names:
            await update.message.reply_text("❌ В архиве не найдено картинок!")
            return WAIT_IMAGE

        total = len(names)
        await update.message.reply_text(f"🔍 Нашёл {total} фото, создаю архив...\nЭто может занять немного времени ⏳")

        zip_result = await process_batch_to_zip(update, names, zf, tmpl)

    await update.message.reply_document(
        document=zip_result,
        filename="result.zip",
        caption=f"🎉 Готово! {total} фото → {total*2} картинок в архиве"
    )
    context.user_data.clear()
    return WAIT_IMAGE

async def receive_font(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt not in ["1","2","3","4","5"]:
        await update.message.reply_text("Отправь цифру от 1 до 5 👆")
        return WAIT_FONT
    context.user_data["style"] = txt
    styles = {"1":"Обычный","2":"Жирный","3":"Неон","4":"Тень","5":"Обводка"}
    await update.message.reply_text(f"✅ Стиль: {styles[txt]}\n\n{SIZE_MENU}")
    return WAIT_SIZE

async def receive_size(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    try:
        size = int(txt)
        if size < 20 or size > 400:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Напиши число от 20 до 400\nНапример: 100")
        return WAIT_SIZE
    context.user_data["font_size"] = size
    await update.message.reply_text(
        f"✅ Размер: {size}\n\n"
        "📝 Отправь текст для первой картинки\n(например: этот трек>>>)"
    )
    return WAIT_TEXT1

async def receive_text1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["text1"] = update.message.text
    await update.message.reply_text("✅ Принято!\n\n🎵 Теперь отправь текст трека для второй картинки")
    return WAIT_TEXT2

async def receive_text2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ud = context.user_data
    settings = {
        "style":     ud.get("style", "1"),
        "font_size": ud.get("font_size", 100),
        "text1":     ud.get("text1", "этот трек>>>"),
        "text2":     update.message.text,
    }
    await update.message.reply_text("⏳ Создаю картинки...")
    await process_one(update, ud["image"], settings)
    save_template(settings)
    await update.message.reply_text(
        "✅ Готово! Шаблон сохранён 🔖\n\n"
        "Теперь кидай картинку или zip с кучей фоток!\n"
        "/newtemplate — изменить шаблон"
    )
    context.user_data.clear()
    return WAIT_IMAGE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Отменено. /start чтобы начать")
    return ConversationHandler.END

def main():
    ensure_font()
    app = Application.builder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("newtemplate", new_template),
            MessageHandler(filters.PHOTO | filters.Document.IMAGE, receive_image),
            MessageHandler(filters.Document.FileExtension("zip"), receive_zip),
        ],
        states={
            WAIT_IMAGE: [
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, receive_image),
                MessageHandler(filters.Document.FileExtension("zip"), receive_zip),
                CommandHandler("newtemplate", new_template),
            ],
            WAIT_FONT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_font)],
            WAIT_SIZE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_size)],
            WAIT_TEXT1: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text1)],
            WAIT_TEXT2: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text2)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv)
    print("🤖 Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
