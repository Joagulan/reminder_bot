import logging
from telegram.ext import CommandHandler, MessageHandler, Filters, RegexHandler, ConversationHandler, Updater, run_async
from telegram import (ReplyKeyboardMarkup)
import dateparser
from datetime import datetime
import config
import db
from db import User, Note, Reminder, Category


updater = Updater(token=config.token)
dispatcher = updater.dispatcher
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
job = updater.job_queue


def build_menu(buttons,
               n_cols,
               header_buttons=None,
               footer_buttons=None):
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, header_buttons)
    if footer_buttons:
        menu.append(footer_buttons)
    return menu


back_button = 'Назад'

cancel_reply_markup = ReplyKeyboardMarkup(build_menu([back_button], n_cols=2),
                                          resize_keyboard=True)


def start(bot, update):
    """Стартовое меню"""

    session = db.session

    # узнаем id телеграма пользователя
    user_id = update.message.chat_id

    # создаем меню
    reply_keyboard = ['📓 Заметки', '⏰ Напоминания']
    main_reply_markup = ReplyKeyboardMarkup(build_menu(reply_keyboard, n_cols=1), resize_keyboard=True)

    update.message.reply_text('Выберите нужный Вам пункт:', reply_markup=main_reply_markup)

    # проверяем наличие пользователя в базе данных
    chek_user_id = session.query(User).filter_by(id=user_id).one_or_none()

    # если пользователя нет в бд, то добавляем
    if not chek_user_id:
        session.add(User(id=user_id))
        session.commit()

    return -1


def notes(bot, update):
    """Меню заметок"""

    reply_keyboard = ["Мои заметки", "Категории"]
    reply_markup = ReplyKeyboardMarkup(build_menu(reply_keyboard, n_cols=2, footer_buttons=[back_button]),
                                       resize_keyboard=True, one_time_keyboard=True)
    update.message.reply_text('Выберите нужный Вам пункт:', reply_markup=reply_markup)

    return 'notes_menu'


def my_notes(bot, update):
    """Меню управления заметками"""

    # создаем меню заметок
    reply_keyboard = ["Мои заметки", "Добавить заметку", "Удалить заметку"]
    reply_markup = ReplyKeyboardMarkup(build_menu(reply_keyboard, n_cols=2, footer_buttons=[back_button]),
                                   resize_keyboard=True, one_time_keyboard=True)
    update.message.reply_text('Выберите нужный Вам пункт:', reply_markup=reply_markup)
    return 'add_or_del_notes'


def ask_category_for_notes(bot, update):
    """Отображение категорий заметок"""

    session = db.session

    user_id = update.message.chat_id

    categories = ['Без категории']
    search_categories = session.query(Category).filter_by(user_id=user_id)
    for row in search_categories:
        categories.append(row.name_of_category)

    reply_markup = ReplyKeyboardMarkup(build_menu(categories, n_cols=2, footer_buttons=[back_button]),
                                       resize_keyboard=True, one_time_keyboard=True)
    update.message.reply_text('Выберите категорию', reply_markup=reply_markup)

    return 'ask_category_for_notes'


def display_notes(bot, update):
    """Отображение заметок категории"""

    session = db.session

    user_id = update.message.chat_id
    category = update.message.text

    # проверяем наличие заметок в категории
    if category == 'Без категории':
        chosen_notes = session.query(Note).filter_by(user_id=user_id, category=None)

        # если заметок в категории нет, то отображаем сообщение об отсутвии
        if chosen_notes.count() == 0:
            update.message.reply_text('В этой категории список заметок пуст.')

            return notes(bot, update)

        # если есть, то выводим их на экран
        else:
            for note in chosen_notes:
                update.message.reply_text(f'{note.text}')

        return notes(bot, update)

    # тоже самое для других категорий
    else:
        notes_in_category = session.query(Category).filter_by(name_of_category=category, user_id=user_id)
        chosen_notes = session.query(Note).filter_by(user_id=user_id, category_id=notes_in_category[0].id)
        if chosen_notes.count() == 0:
            update.message.reply_text('В этой категории список заметок пуст.')

            return notes(bot, update)
        else:
            for note in chosen_notes:
                update.message.reply_text(f'{note.text}')

            return notes(bot, update)


def note_text(bot, update):
    """Получаем текст заметки"""

    update.message.reply_text("Введите текст заметки.", reply_markup=cancel_reply_markup)

    return 'add_note'


def add_note(bot, update):
    """Добавляем заметку в бд"""

    session = db.session

    user_id = update.message.chat_id
    text = update.message.text

    session.add(Note(user_id=user_id, text=text))
    session.commit()

    # проверяем есть ли у пользователя созданные категории
    created_categories = session.query(Category).filter_by(user_id=user_id).count()

    # если нет созданных категорий, то добавляем без категории
    if created_categories == 0:
        update.message.reply_text("Заметка успешно добавлена")
        return start(bot, update)

    # если есть созданные категории, то выводим их пользователю для выбора
    else:
        list_of_categories = ["Без категории"]
        for cat in session.query(Category).filter_by(user_id=user_id):
            list_of_categories.append(cat.name_of_category)
        reply_markup = ReplyKeyboardMarkup(build_menu(list_of_categories, n_cols=2, footer_buttons=[back_button]),
                                           resize_keyboard=True, one_time_keyboard=True)
        update.message.reply_text('Выберите категорию', reply_markup=reply_markup)

        return 'chose_category_for_note'


def add_category_for_note(bot, update):
    """Добавляем категорию к заметке"""

    session = db.session

    user_id = update.message.chat_id
    category = update.message.text

    # ищем последнюю добавленную пользователем заметку
    last_note = session.query(Note).filter_by(user_id=user_id)

    # находим id выбранной категории
    category_search = session.query(Category).filter_by(name_of_category=category, user_id=user_id)
    category_id = category_search[0].id

    # добавляем к заметке выбранную категорию
    last_note[-1].category_id = category_id
    session.dirty
    session.commit()

    update.message.reply_text('Категория выбрана.')
    return start(bot, update)


def select_note_to_delete(bot, update):
    """Вывод всех заметок на экран для выбора"""

    session = db.session

    user_id = update.message.chat_id

    # ищем все заметки пользователя
    user_notes = session.query(Note).filter_by(user_id=user_id)

    # если заметок нет, то возвращаем пользователя в главное меню
    if user_notes.count() == 0:
        update.message.reply_text("Список заметок пуст.")

        return notes(bot, update)

    # если заметки есть, то выкидываем все заметки на экран
    else:
        for note in user_notes:
            update.message.reply_text(f"id заметки: {note.id}.\n Категория: {note.category}.\n{note.text}")
        update.message.reply_text("Введите id заметки, которую хотите удалить", reply_markup=cancel_reply_markup)

        return 'delete_note'


def delete_note(bot, update):
    """Удаление заметки"""

    session = db.session

    user_id = update.message.chat_id
    notes_id = update.message.text

    # удостоверяемся, что строка состоит только из цифр
    if notes_id.isnumeric() is True:

        # проверяем наличие введенного id
        note_in_db = session.query(Note).filter_by(user_id=user_id, id=notes_id)

        # если не найдено, то id введен не верно
        if not note_in_db.one_or_none():
            update.message.reply_text("id заметки введен не верно.")

            return select_note_to_delete(bot, update)
        else:
            session.delete(note_in_db[0])
            session.commit()
            update.message.reply_text("Заметка успешно удалена.")

            return start(bot, update)
    else:
        update.message.reply_text("id заметки введен не верно.")

        return select_note_to_delete(bot, update)


def user_categories_menu(bot, update):
    """Меню категорий"""

    reply_keyboard = ['Мои категории', 'Добавить категорию', 'Удалить категорию']
    reply_markup = ReplyKeyboardMarkup(build_menu(reply_keyboard, n_cols=1, footer_buttons=[back_button]),
                                       resize_keyboard=True)
    update.message.reply_text('Выберите нужный пункт.', reply_markup=reply_markup)

    return 'categories_menu'


def display_users_categories(bot, update):
    """Отображение всех категорий пользователя"""

    session = db.session

    user_id = update.message.chat_id

    # проверяем наличие категорий у пользователя
    user_categories = session.query(Category).filter_by(user_id=user_id)

    # если категорий нет, то возвращаем в предыдущее меню
    if user_categories.count() == 0:
        update.message.reply_text('У Вас еще нет категорий.')

        return 'categories_menu'

    # если категории есть, то отображаем их на экране пользователя
    else:
        for category in user_categories:
            update.message.reply_text(category.name_of_category)

    return 'categories_menu'


def ask_category_name(bot, update):
    """Спрашиваем название новой категории"""

    update.message.reply_text('Введите название категории.', reply_markup=cancel_reply_markup)

    return 'add_category'


def add_category(bot, update):
    """Добавляем новую категорию"""

    session = db.session

    user_id = update.message.chat_id
    name_of_category = update.message.text

    # проверяем наличие такой категории в бд
    user_categories = session.query(Category).filter_by(user_id=user_id)

    for category in user_categories:
        if category.name_of_category.lower() == name_of_category.lower():
            update.message.reply_text('Такая категория уже существует.')

            return 'categories_menu'

        else:
            continue

    # добавляем категорию в бд
    category = Category(name_of_category=name_of_category, user_id=user_id)
    session.add(category)
    session.commit()

    update.message.reply_text('Категория успешно добавлена.')

    return start(bot, update)


def ask_which_category_to_delete(bot, update):
    """Выбор категори для удаления"""

    session = db.session

    user_id = update.message.chat_id

    # проверяем наличие категорий у пользователя
    user_categories = session.query(Category).filter_by(user_id=user_id)

    # если категорий нет, то возвращаем в предыдущее меню
    if user_categories.count() == 0:
        update.message.reply_text('У Вас еще нет категорий.')

        return 'categories_menu'

    # если есть отображаем их в виде кнопок для выбора
    else:
        categories = []
        for category in session.query(Category).filter_by(user_id=user_id):
            categories.append(category.name_of_category)

        reply_markup = ReplyKeyboardMarkup(build_menu(categories, n_cols=2, footer_buttons=[back_button]),
                                           resize_keyboard=True, one_time_keyboard=True)
        update.message.reply_text('Выберите категорию для удаления.', reply_markup=reply_markup)

    return 'delete_category'


def delete_category(bot, update):
    """Удаление выбранной категории"""

    session = db.session

    user_id = update.message.chat_id
    name_of_category = update.message.text

    # находим id выбранной категории
    category_search = session.query(Category).filter_by(name_of_category=name_of_category, user_id=user_id)
    category_id = category_search[0].id

    # переводим все заметки с удаляемой категории в категорию "Без категории"
    notes_from_deleting_category = session.query(Note).filter_by(category_id=category_id, user_id=user_id)
    if notes_from_deleting_category.count() != 0:
        for note in notes_from_deleting_category:
            note.category = None
            session.dirty
            session.commit()

    # удаляем категорию
    remove_category = session.query(Category).filter_by(name_of_category=name_of_category, user_id=user_id)
    session.delete(remove_category[0])
    session.commit()

    update.message.reply_text('Категория успешно удалена.')

    return start(bot, update)


def reminder_menu(bot, update):
    """Меню напоминаний"""

    reply_keyboard = ['Добавить напоминание', 'Удалить напоминание', 'Мои напоминания']
    reply_markup = ReplyKeyboardMarkup(build_menu(reply_keyboard, n_cols=1, footer_buttons=[back_button]),
                                       resize_keyboard=True, one_time_keyboard=True)
    update.message.reply_text('Выберите нужный пункт.', reply_markup=reply_markup)

    return 'reminder_menu'


def user_reminders(bot, update):
    """Отображение всех напоминаний пользователя"""

    session = db.session

    user_id = update.message.chat_id

    # проверяем наличие напоминаний у пользователя
    all_user_reminders = session.query(Reminder).filter_by(user_id=user_id)

    # проверяем наличие не до конца заполненных напоминаний, если они есть, то удаляем
    for reminder in all_user_reminders:
        if reminder.date is None or reminder.time is None:
            session.delete(reminder)
            session.commit()

        if reminder.notification == 'sent':
            session.delete(reminder)
            session.commit()

    # проверяем наличие напоминаний у пользователя
    if all_user_reminders.count() == 0:
        update.message.reply_text('У Вас еще нет напоминаний.')

        return reminder_menu(bot, update)

    # если напоминания есть, то выводим их на экран
    else:
        for reminder in all_user_reminders:
            update.message.reply_text(f'Дата: {reminder.date}\n Время: {reminder.time}\n '
                                      f'Текст напоминания:\n {reminder.text}')

        return start(bot, update)


def new_reminder_date(bot, update):
    """Дата нового напоминания"""

    update.message.reply_text('Введите дату напоминания в формате ДД.ММ.ГГГГ.', reply_markup=cancel_reply_markup)

    return 'add_date_for_reminder'


def add_date_for_reminder(bot, update):
    """Добавляем дату к новому напоминанию"""

    session = db.session

    user_id = update.message.chat_id

    date = update.message.text

    # проверяем коректность введенной даты
    try:
        date_for_db = dateparser.parse(date).date()

    except AttributeError:

        update.message.reply_text('Вы ввели не правильный формат даты.')

        return new_reminder_date(bot, update)

    else:
        # проверяем не введено ли прошедшее время
        if date_for_db < datetime.now().date():

            update.message.reply_text('Вы ввели прошедшую дату.')

            return new_reminder_date(bot, update)

        # если введено все верно добавляем дату напоминания в бд
        else:
            session.add(Reminder(user_id=user_id, date=date_for_db))
            session.commit()

            update.message.reply_text('Введите время для напоминания в формате ЧЧ:ММ', reply_markup=cancel_reply_markup)

            return 'add_time_for_reminder'


def new_reminder_time(bot, update):
    """Узнаем время для нового напоминания, если допущена ошибка при вводе данных"""

    update.message.reply_text('Введите время для напоминания в формате ЧЧ:ММ', reply_markup=cancel_reply_markup)

    return 'add_time_for_reminder'


def add_time_for_reminder(bot, update):
    """Добавляем время напоминания"""

    session = db.session

    user_id = update.message.chat_id

    time = update.message.text
    date_now = str(datetime.now().date())
    # проверяем коректность введенной даты

    try:
        time_for_db = dateparser.parse(f"{date_now}, {time}").astimezone()

    except AttributeError:

        update.message.reply_text('Вы ввели не правильный формат времени.')

        return new_reminder_time(bot, update)

    # если введено все верно добавляем время напоминания напоминания в бд
    else:
        # находим id последнего добавленного напоминания и добавляем в него информацию о времени
        all_user_reminders = session.query(Reminder).filter_by(user_id=user_id)
        all_user_reminders[-1].time = time_for_db

        session.dirty
        session.commit()

        update.message.reply_text("Введите текст напоминания.", reply_markup=cancel_reply_markup)

        return 'add_text_for_reminder'


def add_text_for_reminder(bot, update):
    """Добавляем текст напоминания"""

    session = db.session

    user_id = update.message.chat_id

    text = update.message.text

    # находим id последнего добавленного напоминания и добавляем в него текст напоминания
    all_user_reminders = session.query(Reminder).filter_by(user_id=user_id)
    all_user_reminders[-1].notification = 'not_sent'
    all_user_reminders[-1].text = text

    session.dirty
    session.commit()

    update.message.reply_text("Напоминание успешно добавлено.")

    return start(bot, update)


def select_reminder_to_delete(bot, update):
    """Вывод всех заметок на экран для выбора"""

    session = db.session

    user_id = update.message.chat_id

    # ищем все напоминания пользователя
    user_reminders = session.query(Reminder).filter_by(user_id=user_id)

    # проверяем наличие не до конца заполненных напоминаний, если они есть, то удаляем
    for reminder in user_reminders:
        if reminder.date is None or reminder.time is None:
            session.delete(reminder)
            session.commit()

        if reminder.notification == 'sent':
            session.delete(reminder)
            session.commit()

    # если заметок нет, то возвращаем пользователя в меню напоминаний
    if user_reminders.count() == 0:
        update.message.reply_text("Список напоминаний пуст.")

        return reminder_menu(bot, update)

    # если напоминания есть, то выкидываем все заметки на экран
    else:
        for reminder in user_reminders:
            update.message.reply_text(f"id напоминания: {reminder.id}.\n Дата: {reminder.date}.\n"
                                      f"Время: {reminder.time}.\n Текст напоминания: {reminder.text}")
        update.message.reply_text("Введите id напоминания которое хотите удалить.", reply_markup=cancel_reply_markup)

        return 'delete_reminder'


def delete_reminder(bot, update):
    """Удаление заметки"""

    session = db.session

    user_id = update.message.chat_id
    reminder_id = update.message.text

    # удостоверяемся, что строка состоит только из цифр
    if reminder_id.isnumeric() is True:

        # проверяем наличие введенного id
        reminder_in_db = session.query(Reminder).filter_by(user_id=user_id, id=reminder_id)

        # если не найдено, то id введен не верно
        if not reminder_in_db.one_or_none():
            update.message.reply_text("id напоминания введен не верно.")

            return select_reminder_to_delete(bot, update)
        else:
            session.delete(reminder_in_db[0])
            session.commit()
            update.message.reply_text("Напоминание успешно удалено.")

            return start(bot, update)
    else:
        update.message.reply_text("id напоминания введен не верно.")

        return select_reminder_to_delete(bot, update)


@run_async
def send_reminder(bot, job):
    """Регуляная проверка отправки напоминания и их отправление"""

    session = db.session

    date = datetime.now().date()

    time = datetime.now().time()

    reminders = session.query(Reminder)

    # проверяем наличие не до конца заполненных напоминаний, если они есть, то удаляем
    for reminder in reminders:

        if reminder.date is None or reminder.time is None:
            session.delete(reminder)
            session.commit()

        # удаляем напоминания, которые уже были отправлены пользователю
        if reminder.notification == 'sent':
            session.delete(reminder)
            session.commit()

        # узнаем пора ли отправить напоминание пользователю
        if reminder.date.strftime('%Y, %m, %d') == date.strftime('%Y, %m, %d'):

            if reminder.time.strftime('%H, %M') == time.strftime('%H, %M'):
                bot.send_message(chat_id=reminder.user_id, text=f'Дата: {reminder.date}\n '
                f'Время: {reminder.time}\n Текст напоминания:\n {reminder.text}')

                reminder.notification = 'sent'
                session.dirty
                session.commit()

            else:
                continue

        else:
            continue


notes_menu_global = ConversationHandler(
    entry_points=[RegexHandler('📓 Заметки', notes)],
    states={
        'notes_menu': [RegexHandler(back_button, start),
                       RegexHandler('Мои заметки', my_notes),
                       RegexHandler('Категории', user_categories_menu)],
        'add_or_del_notes': [RegexHandler(back_button, notes),
                             RegexHandler('Мои заметки', ask_category_for_notes),
                             RegexHandler('Добавить заметку', note_text),
                             RegexHandler('Удалить заметку', select_note_to_delete)],
        'ask_category_for_notes': [RegexHandler(back_button, notes),
                                   MessageHandler(Filters.all, display_notes)],
        'add_note': [RegexHandler(back_button, start),
                     MessageHandler(Filters.all, add_note)],
        'chose_category_for_note': [RegexHandler(back_button, start),
                                    MessageHandler(Filters.all, add_category_for_note)],
        'delete_note': [RegexHandler(back_button, start),
                        MessageHandler(Filters.all, delete_note)],
        'categories_menu': [RegexHandler(back_button, notes),
                            RegexHandler('Мои категории', display_users_categories),
                            RegexHandler('Добавить категорию', ask_category_name),
                            RegexHandler('Удалить категорию', ask_which_category_to_delete)],
        'add_category': [RegexHandler(back_button, user_categories_menu),
                         MessageHandler(Filters.all, add_category)],
        'add_time_for_reminder': [RegexHandler(back_button, user_categories_menu),
                                  MessageHandler(Filters.all, add_time_for_reminder)],
        'delete_category': [RegexHandler(back_button, user_categories_menu),
                            MessageHandler(Filters.all, delete_category)]
    },
    fallbacks=[RegexHandler(back_button, start)]
)

reminders_menu_global = ConversationHandler(
    entry_points=[RegexHandler('⏰ Напоминания', reminder_menu)],
    states={
        'reminder_menu': [RegexHandler(back_button, start),
                          RegexHandler('Добавить напоминание', new_reminder_date),
                          RegexHandler('Удалить напоминание', select_reminder_to_delete),
                          RegexHandler('Мои напоминания', user_reminders)],
        'add_date_for_reminder': [RegexHandler(back_button, reminder_menu),
                                  MessageHandler(Filters.all, add_date_for_reminder)],
        'add_time_for_reminder': [RegexHandler(back_button, reminder_menu),
                                  MessageHandler(Filters.all, add_time_for_reminder)],
        'add_text_for_reminder': [RegexHandler(back_button, reminder_menu),
                                  MessageHandler(Filters.all, add_text_for_reminder)],
        'delete_reminder': [RegexHandler(back_button, reminder_menu),
                            MessageHandler(Filters.all, delete_reminder)]
    },
    fallbacks=[RegexHandler(back_button, start)]
)

job_send_notification = job.run_repeating(send_reminder, interval=60)

dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(notes_menu_global)
dispatcher.add_handler(reminders_menu_global)
updater.start_polling()