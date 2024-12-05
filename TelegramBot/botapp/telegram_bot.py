from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from asgiref.sync import sync_to_async
from botapp.models import Product, User, Cart, Purchase

# Хранилище для сессий пользователей
sessions = {}

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Добро пожаловать! Используйте /login для входа или /register для регистрации."
    )

# Обработчик команды /register
async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("Используйте: /register <username> <password> <role (admin/customer)>")
        return

    username, password, role = args[0], args[1], args[2]
    if role not in ['admin', 'customer']:
        await update.message.reply_text("Роль должна быть 'admin' или 'customer'.")
        return

    # Проверка существования пользователя
    user_exists = await sync_to_async(User.objects.filter(username=username).exists)()
    if user_exists:
        await update.message.reply_text("Пользователь с таким именем уже существует.")
        return

    # Создание пользователя
    await sync_to_async(User.objects.create)(username=username, password=password, role=role)
    await update.message.reply_text(f"Регистрация успешна! Ваш логин: {username}")

# Обработчик команды /login
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Используйте: /login <username> <password>")
        return

    username, password = args[0], args[1]
    try:
        user = await sync_to_async(User.objects.get)(username=username, password=password)
        sessions[update.message.chat_id] = user
        await update.message.reply_text(f"Добро пожаловать, {user.username}! Вы вошли как {user.role}.")
    except User.DoesNotExist:
        await update.message.reply_text("Неверный логин или пароль.")

# Обработчик команды /list
async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id not in sessions:
        await update.message.reply_text("Пожалуйста, войдите с помощью /login.")
        return

    products = await sync_to_async(list)(Product.objects.all())
    if products:
        response = "\n".join([f"{p.id}. {p.name} - {p.price}₽" for p in products])
    else:
        response = "Список товаров пуст."
    await update.message.reply_text(response)

# Обработчик команды /add_product (только для админа)
async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id not in sessions:
        await update.message.reply_text("Пожалуйста, войдите с помощью /login.")
        return

    user = sessions[update.message.chat_id]
    if user.role != 'admin':
        await update.message.reply_text("Только администраторы могут добавлять товары.")
        return

    args = context.args
    if len(args) < 3:
        await update.message.reply_text("Используйте: /add_product <название> <описание> <цена>")
        return

    name, description, price = args[0], " ".join(args[1:-1]), args[-1]
    try:
        price = float(price)
        await sync_to_async(Product.objects.create)(name=name, description=description, price=price)
        await update.message.reply_text(f"Товар '{name}' успешно добавлен!")
    except ValueError:
        await update.message.reply_text("Цена должна быть числом.")

# Обработчик команды /add_to_cart
async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id not in sessions:
        await update.message.reply_text("Пожалуйста, войдите с помощью /login.")
        return

    user = sessions[update.message.chat_id]
    if user.role != 'customer':
        await update.message.reply_text("Только покупатели могут добавлять товары в корзину.")
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Используйте: /add_to_cart <product_id> <quantity>")
        return

    try:
        product_id, quantity = int(args[0]), int(args[1])
        product = await sync_to_async(Product.objects.get)(id=product_id)
        await sync_to_async(Cart.objects.create)(user=user, product=product, quantity=quantity)
        await update.message.reply_text(f"Товар '{product.name}' добавлен в корзину ({quantity} шт.).")
    except Product.DoesNotExist:
        await update.message.reply_text("Товар с таким ID не найден.")
    except ValueError:
        await update.message.reply_text("ID и количество должны быть числовыми.")

# Обработчик команды /purchase
async def purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id not in sessions:
        await update.message.reply_text("Пожалуйста, войдите с помощью /login.")
        return

    user = sessions[update.message.chat_id]
    if user.role != 'customer':
        await update.message.reply_text("Только покупатели могут оформлять покупки.")
        return

    # Извлечение корзины пользователя с предзагрузкой связанных объектов
    cart_items = await sync_to_async(list)(
        Cart.objects.filter(user=user).select_related('product')
    )

    if not cart_items:
        await update.message.reply_text("Ваша корзина пуста.")
        return

    total = 0
    for item in cart_items:
        total += item.product.price * item.quantity
        # Создание записи о покупке
        await sync_to_async(Purchase.objects.create)(
            user=user,
            product=item.product,
            quantity=item.quantity,
            total_price=item.product.price * item.quantity
        )

    # Удаление всех элементов корзины после оформления покупки
    await sync_to_async(Cart.objects.filter(user=user).delete)()
    await update.message.reply_text(f"Покупка оформлена на сумму {total}₽.")


# Основная функция для запуска бота
def main():
    application = Application.builder().token("8138487673:AAHyc1KOmfKKBOQ3GOKXKg-xC0zWjpdfgG4").build()

    # Регистрация команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("register", register))
    application.add_handler(CommandHandler("login", login))
    application.add_handler(CommandHandler("list", list_products))
    application.add_handler(CommandHandler("add_product", add_product))
    application.add_handler(CommandHandler("add_to_cart", add_to_cart))
    application.add_handler(CommandHandler("purchase", purchase))

    # Запуск бота
    application.run_polling()
