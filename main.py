from logger import Logging
from api import basicApiCall, servers, account
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import F
import configparser

BOT_CONFIG = "bot_config.ini"

config_parser = configparser.ConfigParser()
config_parser.read(BOT_CONFIG)

VDSINA_API_TOKEN = config_parser.get("vdsina", "VDSINA_API_TOKEN")
BOT_TOKEN = config_parser.get("telegram", "BOT_TOKEN")
ALLOW_CHAT_ID = config_parser.get("telegram", "CHAT_ID")
BOT_LOGGER_NAME = config_parser.get("logger", "BOT_LOGGER_NAME")
BOT_LOGFILE = config_parser.get("logger", "BOT_LOGFILE")

bot = Bot(BOT_TOKEN)
logger = Logging(BOT_LOGGER_NAME, BOT_LOGFILE)
api_instance = basicApiCall(VDSINA_API_TOKEN, logger)
servers_api = servers(api_instance.hoster_token, api_instance.logger)
account_api = account(api_instance.hoster_token, api_instance.logger)
dp = Dispatcher()

def servers_callback_mapping(keyboard_data):
    button_map = {}
    for row in keyboard_data:
        for button in row:
            button_map[button.callback_data] = button.text
    return button_map

def builder_server_keyboard(servers, callback_data_prefix):
    builder = InlineKeyboardBuilder()
    for text, callback_data_name in servers.items():
        callback_data_name = callback_data_name.replace("-", "_")
        builder.add(
            types.InlineKeyboardButton(text=text, callback_data=f"{callback_data_prefix}_{callback_data_name}")
        )
    return builder

@dp.message(Command("start"))
async def start(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="Проверить баланс", callback_data="vdsina_main_balance_status"),
        types.InlineKeyboardButton(text="Прогноз отключения", callback_data="vdsina_main_account_data")
    )

    builder.row(
        types.InlineKeyboardButton(text="Мои сервера", callback_data="vdsina_main_servers_params"),
        types.InlineKeyboardButton(text="Мониторинг серверов", callback_data="vdsina_main_servers_stats")
    )

    builder.row(
        types.InlineKeyboardButton(text="Помощь", callback_data="help")
    )

    await message.answer(
        "Выберите что вас интересует из меню ниже:",
        reply_markup=builder.as_markup()
    )
    
@dp.message(Command("balance"))
async def balance_status(message: types.Message):
    if message.chat.id == int(ALLOW_CHAT_ID):
        balance_message = account_api.get_balance()
        await message.answer(balance_message)
        logger.info("Запрос статуса в чате: %s", message.chat.id)
    else:
        await message.answer("Это операция не разрешена для этого чата")

@dp.message(Command("account_forecast"))
async def account_forecast(message: types.Message):
    if message.chat.id == int(ALLOW_CHAT_ID):
        account_message = account_api.get_forecast()
        await message.answer(account_message)
        logger.info("Запрос прогноза отключения в чате: %s", message.chat.id)
    else:
        await message.answer("Это операция не разрешена для этого чата")

@dp.message(Command("help"))
async def help_cmd(message: types.Message):
    await message.answer("Для началы работы с ботом напишите /start")

@dp.callback_query(F.data == "help")
async def help(callback: types.CallbackQuery):
    await callback.message.answer("Для началы работы с ботом напишите /start")

@dp.callback_query(F.data.startswith("vdsina_main"))
async def vdsina_main_callback_process(callback: types.CallbackQuery):
    if callback.message.chat.id == int(ALLOW_CHAT_ID):
        if callback.data == "vdsina_main_balance_status":
            balance_message = account_api.get_balance()
            await callback.message.answer(balance_message)
            logger.info("Запрос статуса в чате: %s", callback.message.chat.id)
        elif callback.data == "vdsina_main_account_data":
            account_message = account_api.get_forecast()
            await callback.message.answer(account_message)
            logger.info("Запрос прогноза отключения в чате: %s", callback.message.chat.id)
        elif callback.data == "vdsina_main_servers_params":
            servers = servers_api.get_servers_name()
            builder = builder_server_keyboard(servers, "vdsina_servers_params")
            await callback.message.answer("Выберите сервер:", reply_markup=builder.as_markup())
        elif callback.data == "vdsina_main_servers_stats":
            servers = servers_api.get_servers_name()
            builder = builder_server_keyboard(servers, "vdsina_servers_stats")
            await callback.message.answer("Выберите сервер:", reply_markup=builder.as_markup())
    else:
        await callback.message.answer("Это операция не разрешена для этого чата")

@dp.callback_query(F.data.startswith("vdsina_servers_params"))
async def vdsina_servers_params_callback_process(callback: types.CallbackQuery):
    button_map = servers_callback_mapping(callback.message.reply_markup.inline_keyboard)
    message = servers_api.get_server_params(button_map[callback.data])
    await callback.message.answer(message)
    logger.info("Запрос параметров сервера: %s, в чате: %s", button_map[callback.data], callback.message.chat.id)

@dp.callback_query(F.data.startswith("vdsina_servers_stats"))
async def vdsina_servers_stats_callback_process(callback: types.CallbackQuery):
    button_map = servers_callback_mapping(callback.message.reply_markup.inline_keyboard)
    images_path = servers_api.get_server_monitoring(button_map[callback.data])
    if images_path is not None:
        for image in images_path:
            caption = image.split("/")[1].replace(".png", "").upper()
            await callback.message.answer_photo(types.FSInputFile(path=image), caption=caption)
        logger.info("Запрос мониторинга сервера: %s, в чате: %s", button_map[callback.data], callback.message.chat.id)
    else:
       await callback.message.answer("Не удалось отправить графики")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
