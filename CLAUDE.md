# Reminder Bot

This project is my personal reminder bot, designed to unclog by saved messages in Telegram with reminders I send myself.

Basically, I used to just type "STUDY FOR EXAM TOMORROW" or "Order the meds, make tax report by April 15"

Now I want the bot to do:

1. Receive my (vague) message, and then delete it from the chat
2. Use OpenAI to create more polished message, like "ORDER VITAMINS AND PROBIOTICS, cancel LinkedIn premium by January 20" into two separate messages "Order vitamins and probiotics" and "Cancel LinkedIn premium, 20 January 2025" (for time clarification let AI use current date and a calendar with current week + previous and next week mapping of day names to dates, so when I say Tuesday next week it finds exact date and prints it.)
3. Each cleaned message it sends as message to me, but this message must include the button "(green square and check mark icon) Done" and "(red X icon) Cancel", and if I press any of them -- message is deleted from the chat.

in .env.local I defined:
OPENAI_API_KEY=<key>
TELEGRAM_BOT_TOKEN=<key>

actual values are in .env