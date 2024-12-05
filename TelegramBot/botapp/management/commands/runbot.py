from django.core.management.base import BaseCommand
from botapp.telegram_bot import main

class Command(BaseCommand):
    help = "Запуск Telegram-бота"

    def handle(self, *args, **kwargs):
        main()