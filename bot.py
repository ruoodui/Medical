import os
import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)
import telegram

# الحصول على التوكن من متغير البيئة
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("TOKEN environment variable not set")

MAX_RESULTS = 10

CATEGORIES = [
    "دكتور", "صيدلية", "طبيب اسنان", "مركز", "مستشفى", "مختبر",
    "مجمعات", "عيادة", "معالج", "المضمدين والممرضين",
    "التجهيزات الطبية والمخبرية", "عوينات", "مستلزمات"
]

CATEGORY_MAP = {str(i): cat for i, cat in enumerate(CATEGORIES)}

def normalize_text(text):
    text = text.lower().strip()
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = " ".join(text.split())
    return text

# تحميل ملف البيانات من نفس مسار السكربت
df = pd.read_excel("doctors.xlsx")
df.columns = [col.strip() for col in df.columns]
df.fillna("", inplace=True)
for col in ["اسم الطبيب", "العنوان", "التصنيف", "الاختصاص"]:
    df[col] = df[col].astype(str).apply(normalize_text)

START, CATEGORY, SPEC, SEARCH = range(4)

def main_menu_keyboard():
    keyboard = [[InlineKeyboardButton(name, callback_data=f"cat:{i}")] for i, name in CATEGORY_MAP.items()]
    keyboard.append([InlineKeyboardButton("🔍 بحث عام", callback_data="general_search")])
    return InlineKeyboardMarkup(keyboard)

def specializations_keyboard(df_filtered):
    unique_specs = df_filtered["الاختصاص"].dropna().unique().tolist()
    spec_map = {str(i): spec for i, spec in enumerate(unique_specs)}
    keyboard = [[InlineKeyboardButton(spec.title(), callback_data=f"spec:{i}")] for i, spec in spec_map.items()]
    keyboard.append([InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard), spec_map

def search_options_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔍 البحث بالاسم", callback_data="search_by_name")],
        [InlineKeyboardButton("📍 البحث بالموقع", callback_data="search_by_address")],
        [InlineKeyboardButton("📋 عرض جميع النتائج", callback_data="show_all")],
        [InlineKeyboardButton("🔄 تحديث البيانات", callback_data="update_data")],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def try_edit_message(query, text, reply_markup=None):
    try:
        await query.edit_message_text(text=text, reply_markup=reply_markup)
    except telegram.error.BadRequest as e:
        if "Message is not modified" in str(e):
            pass
        else:
            raise

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 أهلاً بك في دليل الأطباء.\n"
        "يرجى اختيار التصنيف:\n\n"
        "لتحديث البيانات التواصل واتساب مع هذا الرقم:\n"
        "07828816508\n"
        "مهندس محمد"
    )
    await update.message.reply_text(
        welcome_text,
        reply_markup=main_menu_keyboard()
    )
    return CATEGORY

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "main_menu":
        context.user_data.clear()
        await try_edit_message(query, "يرجى اختيار التصنيف:", reply_markup=main_menu_keyboard())
        return CATEGORY

    elif data == "back_to_search":
        await try_edit_message(query, "يرجى اختيار طريقة البحث:", reply_markup=search_options_keyboard())
        return SEARCH

    elif data == "update_data":
        text = (
            "لتحديث البيانات التواصل واتساب مع هذا الرقم:\n"
            "07828816508\n"
            "مهندس محمد"
        )
        await try_edit_message(query, text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")],
            [InlineKeyboardButton("🔙 رجوع لاختيار نوع البحث", callback_data="back_to_search")]
        ]))
        return SEARCH

    elif data.startswith("cat:"):
        cat_index = data.split("cat:")[1]
        category = CATEGORY_MAP.get(cat_index)
        if not category:
            await try_edit_message(query, "❌ تصنيف غير معروف، يرجى المحاولة مرة أخرى.")
            return CATEGORY

        category = normalize_text(category)
        context.user_data["selected_category"] = category
        context.user_data.pop("selected_spec", None)

        df_filtered = df[df["التصنيف"] == category]
        unique_specs = df_filtered["الاختصاص"].dropna().unique().tolist()

        if unique_specs:
            keyboard, spec_map = specializations_keyboard(df_filtered)
            context.user_data["spec_map"] = spec_map
            await try_edit_message(query, f"يرجى اختيار الاختصاص ضمن التصنيف: {category.title()}", reply_markup=keyboard)
            return SPEC
        else:
            await try_edit_message(query, f"يرجى اختيار طريقة البحث ضمن التصنيف: {category.title()}", reply_markup=search_options_keyboard())
            return SEARCH

    elif data.startswith("spec:"):
        spec_index = data.split("spec:")[1]
        spec_map = context.user_data.get("spec_map", {})
        spec = spec_map.get(spec_index)
        if not spec:
            await try_edit_message(query, "❌ اختصاص غير معروف، يرجى المحاولة مرة أخرى.")
            return SPEC

        spec = normalize_text(spec)
        context.user_data["selected_spec"] = spec
        await try_edit_message(query, f"تم اختيار الاختصاص: {spec.title()}\nيرجى اختيار طريقة البحث:", reply_markup=search_options_keyboard())
        return SEARCH

    elif data == "general_search":
        context.user_data.clear()
        context.user_data["general_search"] = True
        await try_edit_message(query, "🔍 اكتب ما تريد البحث عنه (بحث عام):",
                               reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]]))
        return SEARCH

    elif data == "search_by_name":
        context.user_data["search_field"] = "اسم الطبيب"
        await try_edit_message(query, "🔍 اكتب اسم الطبيب للبحث:", reply_markup=search_options_keyboard())
        return SEARCH

    elif data == "search_by_address":
        context.user_data["search_field"] = "العنوان"
        await try_edit_message(query, "🔍 اكتب الموقع (العنوان) للبحث:", reply_markup=search_options_keyboard())
        return SEARCH

    elif data == "show_all":
        category = context.user_data.get("selected_category")
        spec = context.user_data.get("selected_spec")

        df_search = df.copy()
        if category:
            category = normalize_text(category)
            df_search = df_search[df_search["التصنيف"] == category]
        if spec:
            spec = normalize_text(spec)
            df_search = df_search[df_search["الاختصاص"] == spec]

        context.user_data["search_results"] = df_search.to_dict(orient="records")
        context.user_data["result_offset"] = 0

        return await show_limited_results(update, context)

    elif data == "show_more":
        return await show_limited_results(update, context)

async def show_limited_results(update_or_context, context):
    results = context.user_data.get("search_results", [])
    offset = context.user_data.get("result_offset", 0)
    chunk = results[offset:offset + MAX_RESULTS]

    if not chunk:
        if hasattr(update_or_context, "callback_query") and update_or_context.callback_query:
            await update_or_context.callback_query.message.reply_text("❌ لا توجد نتائج إضافية.")
        else:
            await update_or_context.message.reply_text("❌ لا توجد نتائج إضافية.")
        return SEARCH

    context.user_data["result_offset"] = offset + MAX_RESULTS
    is_callback = hasattr(update_or_context, "callback_query") and update_or_context.callback_query

    for row in chunk:
        msg = f"""👨‍⚕️ *{row['اسم الطبيب'].title()}*
🏷️ *التصنيف:* {row['التصنيف'].title()}
📍 *العنوان:* {row['العنوان']}
📞 *الهاتف:* {row['رقم الهاتف']}
📌 *الاختصاص:* {row['الاختصاص'].title()}
📝 *ملاحظات:* {row['الملاحظات']}
"""
        if is_callback:
            await update_or_context.callback_query.message.reply_text(msg, parse_mode="Markdown")
        else:
            await update_or_context.message.reply_text(msg, parse_mode="Markdown")

    navigation_buttons = [
        [InlineKeyboardButton("🔙 رجوع لاختيار نوع البحث", callback_data="back_to_search")],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
    ]

    if context.user_data["result_offset"] < len(results):
        navigation_buttons.insert(0, [InlineKeyboardButton("➡️ عرض المزيد", callback_data="show_more")])

    if is_callback:
        await update_or_context.callback_query.message.reply_text(
            "يرجى اختيار أحد الخيارات:",
            reply_markup=InlineKeyboardMarkup(navigation_buttons)
        )
    else:
        await update_or_context.message.reply_text(
            "يرجى اختيار أحد الخيارات:",
            reply_markup=InlineKeyboardMarkup(navigation_buttons)
        )

    return SEARCH

async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip().lower()
    category = context.user_data.get("selected_category")
    spec = context.user_data.get("selected_spec")
    search_field = context.user_data.get("search_field")

    df_search = df.copy()
    if category:
        category = normalize_text(category)
        df_search = df_search[df_search["التصنيف"] == category]
    if spec:
        spec = normalize_text(spec)
        df_search = df_search[df_search["الاختصاص"] == spec]

    if search_field in ["اسم الطبيب", "العنوان"]:
        results_df = df_search[df_search[search_field].str.contains(query, case=False, na=False)]
    else:
        results_df = df_search[
            df_search["اسم الطبيب"].str.contains(query, case=False, na=False) |
            df_search["العنوان"].str.contains(query, case=False, na=False)
        ]

    context.user_data["search_results"] = results_df.to_dict(orient="records")
    context.user_data["result_offset"] = 0

    if results_df.empty:
        await update.message.reply_text(
            "❌ لم يتم العثور على نتائج.",
            reply_markup=search_options_keyboard()
        )
        return SEARCH

    return await show_limited_results(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم إنهاء المحادثة، شكراً لاستخدامك البوت.")
    return ConversationHandler.END

def main():
    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CATEGORY: [CallbackQueryHandler(handle_buttons)],
            SPEC: [CallbackQueryHandler(handle_buttons)],
            SEARCH: [
                MessageHandler(filters.TEXT & (~filters.COMMAND), handle_search),
                CallbackQueryHandler(handle_buttons)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )

    app.add_handler(conv_handler)
    app.run_polling()

if __name__ == "__main__":
    main()
