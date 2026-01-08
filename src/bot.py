import os
import logging
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from openai import OpenAI
from aiohttp import web

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Initialize Telegram bot
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')


def get_calendar_context():
    """Generate calendar context for the current week, previous week, and next week."""
    today = datetime.now()

    # Calculate start of current week (Monday)
    current_week_start = today - timedelta(days=today.weekday())

    # Previous week
    prev_week_start = current_week_start - timedelta(days=7)

    # Next week
    next_week_start = current_week_start + timedelta(days=7)

    calendar_text = f"Current date: {today.strftime('%A, %B %d, %Y')}\n\n"

    # Previous week
    calendar_text += "Previous week:\n"
    for i in range(7):
        day = prev_week_start + timedelta(days=i)
        calendar_text += f"  {day.strftime('%A')}: {day.strftime('%B %d, %Y')}\n"

    # Current week
    calendar_text += "\nCurrent week:\n"
    for i in range(7):
        day = current_week_start + timedelta(days=i)
        calendar_text += f"  {day.strftime('%A')}: {day.strftime('%B %d, %Y')}\n"

    # Next week
    calendar_text += "\nNext week:\n"
    for i in range(7):
        day = next_week_start + timedelta(days=i)
        calendar_text += f"  {day.strftime('%A')}: {day.strftime('%B %d, %Y')}\n"

    return calendar_text


async def parse_and_polish_message(user_message: str) -> list[str]:
    """Use OpenAI to parse and polish the user's reminder message."""
    calendar_context = get_calendar_context()

    system_prompt = f"""You are a helpful assistant that parses and polishes reminder messages.

{calendar_context}

Your task:
1. Parse the user's vague reminder message
2. Split it into separate tasks if there are multiple tasks mentioned
3. Polish each task to be clear and concise
4. If a date or time is mentioned (like "tomorrow", "next Tuesday", "by April 15"), convert it to the actual date using the calendar above
5. If the message mentions a deadline or says "by [date]", include "do by" before the date
6. Format each reminder as:
   - If date is mentioned: "Task description\\n\\nDate" (task, blank line, date)
   - If no date: just "Task description"

Return ONLY the polished reminders separated by "---". Do not add any explanations or extra text.

Examples:
Input: "STUDY FOR EXAM TOMORROW"
Output: Study for exam

January 9, 2026

Input: "Order the meds, make tax report by April 15"
Output: Order the meds
---
Make tax report

do by April 15, 2026

Input: "Call mom on Tuesday next week and buy groceries"
Output: Call mom

January 14, 2026
---
Buy groceries"""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
            max_tokens=500
        )

        polished_text = response.choices[0].message.content.strip()

        # Split by "---" separator to get individual reminders
        reminders = [reminder.strip() for reminder in polished_text.split('---') if reminder.strip()]

        return reminders

    except Exception as e:
        logger.error(f"Error parsing message with OpenAI: {e}")
        # Fallback: return original message as single reminder
        return [user_message]


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command."""
    await update.message.reply_text(
        "Welcome to Reminder Bot!\n\n"
        "Send me your reminders and I'll organize them for you.\n"
        "Example: 'STUDY FOR EXAM TOMORROW' or 'Order meds, pay bills by Friday'\n\n"
        "I'll clean up your message and send back organized reminders with Done/Cancel buttons."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming reminder messages."""
    user_message = update.message.text
    chat_id = update.message.chat_id
    message_id = update.message.message_id

    # Delete the original message
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.error(f"Error deleting message: {e}")

    # Parse and polish the message using OpenAI
    reminders = await parse_and_polish_message(user_message)

    # Send each reminder with Done/Cancel buttons
    for reminder in reminders:
        # Create inline keyboard with Done and Cancel buttons
        keyboard = [
            [
                InlineKeyboardButton("✅ Done", callback_data=f"done"),
                InlineKeyboardButton("❌ Cancel", callback_data=f"cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send the polished reminder
        await context.bot.send_message(
            chat_id=chat_id,
            text=reminder,
            reply_markup=reply_markup
        )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button presses (Done/Cancel)."""
    query = update.callback_query
    await query.answer()

    # Delete the message when either button is pressed
    try:
        await query.message.delete()
    except Exception as e:
        logger.error(f"Error deleting message after button press: {e}")


async def health_check(_request):
    """Health check endpoint."""
    return web.Response(text='OK', status=200)


async def start_health_server():
    """Start the health check HTTP server."""
    app = web.Application()
    app.router.add_get('/health', health_check)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logger.info("Health check server started on port 8080")

    # Keep the server running
    await asyncio.Event().wait()


async def start_bot():
    """Start the Telegram bot."""
    # Create the Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))

    # Initialize and start the bot
    logger.info("Bot is starting...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)

    # Keep the bot running
    await asyncio.Event().wait()


async def main():
    """Start both the bot and health check server."""
    # Run both the bot and health server concurrently
    await asyncio.gather(
        start_bot(),
        start_health_server()
    )


if __name__ == '__main__':
    asyncio.run(main())
