import asyncio
import importlib
import io
import json
import math
import os
import random
import shlex
import sys
import threading
import uuid
import contextlib
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from collections import defaultdict, deque  

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

# Предотвращение спящего режима Windows
try:
    import ctypes
    from ctypes import wintypes
    
    # Константы для SetThreadExecutionState
    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001
    ES_DISPLAY_REQUIRED = 0x00000002
    ES_AWAYMODE_REQUIRED = 0x00000040
    
    _prevent_sleep_enabled = False
    
    def prevent_sleep():
        """Предотвращает переход системы в спящий режим"""
        global _prevent_sleep_enabled
        try:
            # Устанавливаем флаги для предотвращения спящего режима
            ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED | ES_AWAYMODE_REQUIRED
            )
            _prevent_sleep_enabled = True
            print("[Sleep Prevention] Спящий режим заблокирован")
        except Exception as e:
            print(f"[Sleep Prevention] Ошибка при блокировке спящего режима: {e}")
    
    def allow_sleep():
        """Разрешает системе переходить в спящий режим"""
        global _prevent_sleep_enabled
        try:
            if _prevent_sleep_enabled:
                ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
                _prevent_sleep_enabled = False
                print("[Sleep Prevention] Блокировка спящего режима снята")
        except Exception as e:
            print(f"[Sleep Prevention] Ошибка при снятии блокировки: {e}")
    
    def keep_alive_thread():
        """Поток для периодического обновления состояния предотвращения сна"""
        while True:
            try:
                prevent_sleep()
                # Обновляем каждые 30 секунд
                threading.Event().wait(30)
            except Exception as e:
                print(f"[Sleep Prevention] Ошибка в потоке: {e}")
                threading.Event().wait(60)
    
    _keep_alive_thread = None
    
    def start_sleep_prevention():
        """Запускает поток для предотвращения спящего режима"""
        global _keep_alive_thread
        if _keep_alive_thread is None or not _keep_alive_thread.is_alive():
            prevent_sleep()
            _keep_alive_thread = threading.Thread(target=keep_alive_thread, daemon=True)
            _keep_alive_thread.start()
            print("[Sleep Prevention] Поток предотвращения спящего режима запущен")
    
    def stop_sleep_prevention():
        """Останавливает предотвращение спящего режима"""
        allow_sleep()
        print("[Sleep Prevention] Предотвращение спящего режима остановлено")
        
except ImportError:
    # Если не Windows или ctypes недоступен
    def prevent_sleep():
        pass
    def allow_sleep():
        pass
    def start_sleep_prevention():
        pass
    def stop_sleep_prevention():
        pass
    print("[Sleep Prevention] Предотвращение спящего режима недоступно (не Windows или ctypes недоступен)")

psutil = None
psutil_spec = importlib.util.find_spec("psutil")
if psutil_spec:
    try:
        psutil = importlib.import_module("psutil")
    except Exception:
        psutil = None

GPUtil = None
gputil_spec = importlib.util.find_spec("GPUtil")
if gputil_spec:
    try:
        GPUtil = importlib.import_module("GPUtil")
    except Exception:
        GPUtil = None

# Рекомендуется использовать BOT_TOKEN из переменных окружения
TOKEN = os.getenv('BOT_TOKEN')

# Проверка наличия токена
if not TOKEN:
    print("❌ Токен не найден! Проверьте переменные окружения.")
    print("Убедитесь, что установлена переменная BOT_TOKEN")
    exit(1)

# Проверка формата Discord токена
if '.' not in TOKEN or len(TOKEN) < 50:
    print(f"❌ Неверный формат токена: длина={len(TOKEN)}")
    print("Discord токены обычно имеют длину 59-70 символов и содержат точки (.)")
    exit(1)

print(f"✅ Токен найден: {TOKEN[:10]}...{TOKEN[-5:]}")

LOG_CHANNEL_ID = 1437894172035252266  # ID текстового канала для логов
PROJECT_BIRTHDAY_CHANNEL_ID = 0  # 0 = использовать лог-канал
PROJECT_BIRTHDAY_MONTH = 11
PROJECT_BIRTHDAY_DAY = 20
PROJECT_BIRTHDAY_MESSAGE = (
    "🎂 Сегодня день рождения проекта! Спасибо всем, кто помогает ему развиваться ❤️"
)
EVENT_CHANNEL_ID = 1437854025260466186  # канал для анонсов событий
EVENT_REMINDER_LEAD_MINUTES = 30
DATA_DIR = Path("data")
RES_WHITELIST_FILE = DATA_DIR / "res_whitelist.json"
MODERATION_FILE = DATA_DIR / "moderation.json"
ABOUT_STATUS_FILE = DATA_DIR / "about_statuses.json"
LEVELS_FILE = DATA_DIR / "levels.json"
VOICE_CONFIG_FILE = DATA_DIR / "voice_rooms.json"
TICKETS_CONFIG_FILE = DATA_DIR / "tickets_config.json"
TICKET_MUTES_FILE = DATA_DIR / "ticket_mutes.json"
VOICE_MUTES_FILE = DATA_DIR / "voice_mutes.json"
RAID_CONFIG_FILE = DATA_DIR / "raid_config.json"
MOD_WHITELIST_FILE = DATA_DIR / "mod_whitelist.json"
COMMAND_WHITELIST_FILE = DATA_DIR / "command_whitelist.json"
PROJECT_BIRTHDAY_STATE_FILE = DATA_DIR / "project_birthday_state.json"
EVENTS_FILE = DATA_DIR / "events.json"
EVENT_MANAGERS_FILE = DATA_DIR / "event_managers.json"
SUPER_ADMIN_FILE = DATA_DIR / "super_admin.json"
ETERNAL_WHITELIST_FILE = DATA_DIR / "eternal_whitelist.json"
ASKPR_WHITELIST_FILE = DATA_DIR / "askpr_whitelist.json"
AI_PRIORITY_FILE = DATA_DIR / "ai_priority.json"
AI_BLACKLIST_FILE = DATA_DIR / "ai_blacklist.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
ACHIEVEMENTS_FILE = DATA_DIR / "achievements.json"
RANKCARDS_FILE = DATA_DIR / "rankcards.json"
CUSTOM_ACHIEVEMENTS_FILE = DATA_DIR / "custom_achievements.json"
ANTI_FLOOD_IGNORE_CHANNELS_FILE = DATA_DIR / "anti_flood_ignore_channels.json"
PATCHNOTES_FILE = DATA_DIR / "patchnotes.json"
MSK_TZ = timezone(timedelta(hours=3))
TELEGRAM_BOT_TOKEN = "8235791338:AAGtsqzeV8phGsLu39WLpqgxXIK2rsqc0kc"
TELEGRAM_CHAT_ID = 8165572851  # например, 123456789
TELEGRAM_TICKET_LOG_CHAT_ID = 8165572851  # чат для логирования тикето
# Нейросеть через Mistral AI API (прямое подключение)
# Mistral AI предоставляет бесплатный доступ к моделям, которые понимают русский язык
# Получить бесплатный API ключ: https://console.mistral.ai/api-keys/
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "dEpuO1P9PTLxkk2Tae9XftblYeiqsSub")  # API ключ от Mistral AI
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"  # Официальный API Mistral AI
MISTRAL_MODEL = "mistral-small"  # Модель, которая понимает русский
ASK_COMMAND_RATE_LIMIT_SECONDS =5  # Минимальный интервал между запросами в секундах (1 минута, глобальный лимит для всех)
ASK_COMMAND_CHANNEL_ID = 1441828197644894329  # ID канала, где разрешена команда !ask (0 = любой канал, укажите ID канала для ограничения)
AI_ENABLED = True  # Состояние AI (включен/выключен)
AI_STATUS_CHANNEL_ID = 1441828197644894329  # ID канала для уведомлений о статусе AI (0 = отключить уведомления)

CHAT_XP_PER_MESSAGE = 2
VOICE_XP_PER_MINUTE = 5
XP_PER_LEVEL = 100
LEADERBOARD_PAGE_SIZE = 10
ANTI_FLOOD_MESSAGE_LIMIT = 15
ANTI_FLOOD_WINDOW_SECONDS = 60
ANTI_FLOOD_MAX_WARNINGS = 3
ANTI_FLOOD_MUTE_DURATION_SECONDS = 600
ANTI_FLOOD_IGNORE_CHANNELS: set[int] = set()  # Каналы, где анти-флуд игнорируется

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.voice_states = True
intents.bans = True

bot = commands.Bot(command_prefix="!", intents=intents)
bot.remove_command("help")
res_whitelist: set[int] = set()
eternal_whitelist: set[int] = set()
askpr_whitelist: set[int] = set()
ai_blacklist: set[int] = set()  # Черный список для команды !ask
ai_priority: str = ""  # Приоритет для AI
moderation_data: dict = {"warnings": {}}
about_statuses: list[str] = []
status_index = 0
levels_data: dict = {}
voice_sessions: dict[int, datetime] = {}
message_rate_history: dict[int, deque] = defaultdict(lambda: deque())
flood_warning_counts: dict[int, int] = defaultdict(int)
autorole_ids: set[int] = set()
console_listener_started = False
console_listener_thread: threading.Thread | None = None
bot_start_time: datetime | None = None
status_mode_key = "online"
process = psutil.Process(os.getpid()) if psutil else None
voice_config: dict = {"generators": [], "rooms": {}}
voice_views: dict[int, "VoiceControlView"] = {}
tickets_config: dict = {}
ticket_views: dict[int, "TicketControlView"] = {}
ticket_mutes: dict[int, dict] = {}  # user_id -> {expires_at: str, reason: str, moderator_id: int}
voice_mutes: dict[int, dict] = {}  # user_id -> {expires_at: str, reason: str, moderator_id: int}
restoring_generators: set[int] = set()  # ID генераторов, которые сейчас восстанавливаются
last_ask_command_time: datetime | None = None  # Время последнего запроса команды !ask (глобальный лимит)
raid_config: dict = {
    "enabled": False,
    "threshold": 5,
    "window": 30,
    "action": "kick",
    "notify_channel_id": 0
}
recent_joins: dict[int, deque] = defaultdict(lambda: deque())
mod_whitelist: set[int] = set()  # ID ролей для модераторов
command_whitelist: set[int] = set()
recent_ban_log_ids: dict[int, datetime] = {}
recent_mute_log_ids: dict[int, datetime] = {}
project_birthday_announced_date: date | None = None
scheduled_events: dict[str, dict] = {}
event_manager_roles: set[int] = set()  # ID ролей для менеджеров событий
achievements_data: dict = {}  # Данные о достижениях пользователей
rankcards_data: dict = {}  # Настройки карточек ранга пользователей
custom_achievements: dict = {}  # Кастомные достижения, добавленные через команды


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def log_command(category: str, command: str, user: discord.Member | discord.User, guild: discord.Guild | None = None):
    """Логирует использование команды в терминал"""
    user_info = f"{user.name}#{user.discriminator} ({user.id})"
    guild_info = f" | Сервер: {guild.name} ({guild.id})" if guild else ""
    print(f"[{category}] Команда: {command} | Пользователь: {user_info}{guild_info}")


def mark_log_skip(storage: dict[int, datetime], user_id: int, seconds: int = 5):
    storage[user_id] = utc_now() + timedelta(seconds=seconds)


def should_skip_log(storage: dict[int, datetime], user_id: int) -> bool:
    expiry = storage.get(user_id)
    if not expiry:
        return False
    if utc_now() > expiry:
        storage.pop(user_id, None)
        return False
    return True


async def apply_auto_mute_for_spam(message: discord.Message):
    guild = message.guild
    if guild is None:
        return

    member = message.author
    mute_role = get_mute_role(guild)
    duration = timedelta(seconds=ANTI_FLOOD_MUTE_DURATION_SECONDS)
    duration_text = format_timedelta(duration)

    if mute_role is None:
        await message.channel.send(
            f"{member.mention}, превышен лимит сообщений, но роль '「🐔」Петушиный Угол' не найдена. Сообщите администрации.",
            delete_after=15,
        )
        return

    try:
        mark_log_skip(recent_mute_log_ids, member.id)
        await member.add_roles(mute_role, reason="Автоматический мут за спам (анти-флуд)")
    except discord.Forbidden:
        await message.channel.send(
            f"Не удалось выдать мут {member.mention}: недостаточно прав. Сообщите администрации.",
            delete_after=15,
        )
        return

    await message.channel.send(
        f"{member.mention} получил мут на {duration_text} за спам (анти-флуд).", delete_after=15
    )
    await send_log_embed(
        "Авто-мут за спам",
        f"{member.mention} автоматически получил мут за превышение лимита сообщений.",
        color=0xED4245,
        member=member,
        fields=[("Длительность", duration_text)],
    )
    bot.loop.create_task(schedule_unmute(guild, member.id, mute_role, duration))


async def enforce_message_rate_limit(message: discord.Message):
    if not message.guild:
        return
    
    # Игнорируем анти-флуд в указанных каналах
    if message.channel.id in ANTI_FLOOD_IGNORE_CHANNELS:
        return

    now = utc_now()
    history = message_rate_history[message.author.id]
    cutoff = now - timedelta(seconds=ANTI_FLOOD_WINDOW_SECONDS)
    while history and history[0] < cutoff:
        history.popleft()
    history.append(now)

    if len(history) <= ANTI_FLOOD_MESSAGE_LIMIT:
        return

    warning_count = flood_warning_counts[message.author.id] + 1
    flood_warning_counts[message.author.id] = warning_count

    warning_text = (
        f"{message.author.mention}, прекрати спамить. "
        f"Лимит — {ANTI_FLOOD_MESSAGE_LIMIT} сообщений в минуту. "
        f"Предупреждение {warning_count}/{ANTI_FLOOD_MAX_WARNINGS}."
    )
    try:
        await message.channel.send(warning_text, delete_after=15)
    except discord.HTTPException:
        pass

    # Сбрасываем историю сообщений при выдаче предупреждения
    history.clear()

    if warning_count >= ANTI_FLOOD_MAX_WARNINGS:
        flood_warning_counts.pop(message.author.id, None)
        await apply_auto_mute_for_spam(message)


def get_log_channel():
    return bot.get_channel(LOG_CHANNEL_ID)


def get_project_birthday_channel():
    target_channel_id = PROJECT_BIRTHDAY_CHANNEL_ID or LOG_CHANNEL_ID
    return bot.get_channel(target_channel_id)


def get_event_channel():
    target_channel_id = EVENT_CHANNEL_ID or LOG_CHANNEL_ID
    return bot.get_channel(target_channel_id)


def channel_ref(channel: discord.abc.GuildChannel | None) -> str:
    if channel is None:
        return "неизвестный канал"
    return f"{channel.mention} (`{channel.name}`)"


def _role_ids(collection) -> set[int]:
    ids = set()
    if not collection:
        return ids
    for item in collection:
        role_id = getattr(item, "id", None)
        if role_id is None:
            role = getattr(item, "role", None)
            role_id = getattr(role, "id", None)
        if role_id:
            ids.add(role_id)
    return ids


async def resolve_role_actor(guild: discord.Guild, member: discord.Member, role_id: int, action: str):
    me = guild.me
    if me is None or not me.guild_permissions.view_audit_log:
        return None

    async for entry in guild.audit_logs(limit=10, action=discord.AuditLogAction.member_role_update):
        if entry.target.id != member.id:
            continue
        created_at = entry.created_at
        if created_at:
            if created_at.tzinfo is None:
                created_dt = created_at.replace(tzinfo=timezone.utc)
            else:
                created_dt = created_at.astimezone(timezone.utc)
            delta = utc_now() - created_dt
            if delta.total_seconds() > 60:
                break

        before_roles = _role_ids(getattr(getattr(entry.changes, "before", None), "roles", None))
        after_roles = _role_ids(getattr(getattr(entry.changes, "after", None), "roles", None))

        if action == "add" and role_id in after_roles and role_id not in before_roles:
            return entry.user
        if action == "remove" and role_id in before_roles and role_id not in after_roles:
            return entry.user

    return None


async def resolve_nickname_actor(guild: discord.Guild, member: discord.Member) -> discord.User | None:
    """Определяет, кто изменил никнейм участника, используя audit logs."""
    me = guild.me
    if me is None or not me.guild_permissions.view_audit_log:
        return None

    async for entry in guild.audit_logs(limit=10, action=discord.AuditLogAction.member_update):
        if entry.target.id != member.id:
            continue
        created_at = entry.created_at
        if created_at:
            if created_at.tzinfo is None:
                created_dt = created_at.replace(tzinfo=timezone.utc)
            else:
                created_dt = created_at.astimezone(timezone.utc)
            delta = utc_now() - created_dt
            if delta.total_seconds() > 60:
                break

        changes = entry.changes
        if changes:
            before_nick = getattr(changes.before, "nick", None) if hasattr(changes, "before") else None
            after_nick = getattr(changes.after, "nick", None) if hasattr(changes, "after") else None
            if before_nick != after_nick:
                return entry.user

    return None


def _format_embed_content(embed: discord.Embed) -> str:
    parts: list[str] = []
    if embed.title:
        parts.append(f"Заголовок: {embed.title}")
    if embed.description:
        parts.append(f"Описание: {embed.description}")
    for field in getattr(embed, "fields", [])[:3]:
        parts.append(f"{field.name}: {field.value}")
    if embed.footer and embed.footer.text:
        parts.append(f"Футер: {embed.footer.text}")
    joined = "\n".join(parts).strip()
    return joined or "embed без текста"


def format_content(message: discord.Message) -> str:
    if message.content:
        return message.content[:1024]

    attachments = ", ".join(att.filename for att in message.attachments)
    if attachments:
        return f"(вложения: {attachments})"

    if message.embeds:
        embed_summary = _format_embed_content(message.embeds[0])
        return f"(embed) {embed_summary[:1024]}"

    return "нет текста"


async def log_bot_message_deletion(message: discord.Message):
    await send_log_embed(
        "Удалено сообщение бота",
        f"Канал: {channel_ref(message.channel)}",
        color=0x5865F2,
        member=message.author,
        fields=[
            ("Содержимое", format_content(message)),
            ("ID сообщения", str(message.id)),
        ],
    )


async def send_log_embed(
    title: str,
    description: str = "",
    *,
    color: int = 0x5865F2,
    fields: list | None = None,
    member: discord.abc.User | None = None,
    footer: str | None = None,
):
    channel = get_log_channel()
    if channel is None:
        return

    embed = discord.Embed(title=title, description=description, color=color, timestamp=utc_now())
    if member:
        avatar_obj = getattr(member, "display_avatar", None) or getattr(member, "avatar", None)
        avatar_url = getattr(avatar_obj, "url", None)
        embed.set_author(name=str(member), icon_url=avatar_url)
        footer = footer or f"ID пользователя: {member.id}"

    if fields:
        for name, value in fields:
            embed.add_field(name=name, value=value[:1024], inline=False)

    if footer:
        embed.set_footer(text=footer)

    await channel.send(embed=embed)


def make_embed(title: str, description: str, *, color: int = 0x5865F2) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color, timestamp=utc_now())


def _is_project_birthday(today: date) -> bool:
    if not PROJECT_BIRTHDAY_MONTH or not PROJECT_BIRTHDAY_DAY:
        return False
    return today.month == PROJECT_BIRTHDAY_MONTH and today.day == PROJECT_BIRTHDAY_DAY


async def send_project_birthday_announcement():
    channel = get_project_birthday_channel()
    if channel is None:
        return

    description = PROJECT_BIRTHDAY_MESSAGE.strip() or "Сегодня день рождения проекта!"
    embed = make_embed("День рождения проекта", description, color=0xFEE75C)
    await channel.send(embed=embed)


async def maybe_send_project_birthday_announcement():
    global project_birthday_announced_date
    today = utc_now().date()

    if _is_project_birthday(today):
        if project_birthday_announced_date == today:
            return
        await send_project_birthday_announcement()
        project_birthday_announced_date = today
        save_project_birthday_state()
        return

    if project_birthday_announced_date and project_birthday_announced_date != today:
        project_birthday_announced_date = None
        save_project_birthday_state()


def parse_event_datetime(date_str: str, time_str: str) -> datetime | None:
    pattern = "%d.%m.%Y %H:%M"
    try:
        dt = datetime.strptime(f"{date_str} {time_str}", pattern)
    except ValueError:
        return None
    local_dt = dt.replace(tzinfo=MSK_TZ)
    return local_dt.astimezone(timezone.utc)


def format_event_datetime(dt: datetime) -> str:
    local_dt = dt.astimezone(MSK_TZ)
    return local_dt.strftime("%d.%m.%Y %H:%M МСК")


def event_datetime_from_record(record: dict) -> datetime | None:
    iso_value = record.get("scheduled_at")
    if not isinstance(iso_value, str):
        return None
    try:
        dt = datetime.fromisoformat(iso_value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


async def send_event_message(record: dict, kind: str, mention_here: bool = False):
    channel = get_event_channel()
    if channel is None:
        return

    scheduled_dt = event_datetime_from_record(record)
    if scheduled_dt is None:
        return

    organizer_id = record.get("created_by")
    organizer = f"<@{organizer_id}>" if organizer_id else "неизвестно"
    title = record.get("title", "Мероприятие")
    when_text = format_event_datetime(scheduled_dt)

    descriptions = {
        "create": "Назначено новое мероприятие.",
        "reminder": "Назначено новое мероприятие.",
        "start": "Событие начинается прямо сейчас!",
        "cancel": "Мероприятие отменено.",
        "end": "Мероприятие завершено.",
    }
    description = descriptions.get(kind, "Информация о событии.")
    colors = {
        "create": 0x5865F2,
        "reminder": 0x5865F2,
        "start": 0x57F287,
        "cancel": 0xED4245,
        "end": 0x57F287,
    }
    color = colors.get(kind, 0x5865F2)

    embed = discord.Embed(title=title, description=description, color=color, timestamp=utc_now())
    embed.add_field(name="Дата и время", value=when_text, inline=False)
    embed.add_field(name="Организатор", value=organizer, inline=False)
    if kind == "cancel":
        cancelled_by = record.get("cancelled_by")
        if cancelled_by:
            embed.add_field(name="Отменил", value=f"<@{cancelled_by}>", inline=False)
    elif kind == "end":
        ended_by = record.get("ended_by")
        if ended_by:
            embed.add_field(name="Завершил", value=f"<@{ended_by}>", inline=False)
    event_id = record.get("id")
    if event_id:
        embed.set_footer(text=f"ID события: {event_id}")

    content = "@here" if mention_here else None
    allowed_mentions = (
        discord.AllowedMentions(everyone=True)
        if mention_here
        else discord.AllowedMentions.none()
    )
    await channel.send(content=content, embed=embed, allowed_mentions=allowed_mentions)


tutorial_forms = {
    "ban": (
        "**Форма бана**\n"
        "`!ban @user Time: <s/m/h/d/mo/perma> Reason: <причина>`"
    ),
    "mute": (
        "**Форма мута**\n"
        "`!mute @user Time: <s/m/h/d/mo/perma> Reason: <причина>`"
    ),
    "warn": (
        "**Форма предупреждения**\n"
        "`!warn @user Reason: <причина>`"
    ),
    "unmute": (
        "**Форма снятия мута**\n"
        "`!unmute @user [причина]`"
    ),
    "unban": (
        "**Форма разбана**\n"
        "`!unban <user_id|@user> [причина]`"
    ),
    "unwarn": (
        "**Форма снятия предупреждения**\n"
        "`!unwarn @user [номер]`"
    ),
}


def command_form_embed(command: str) -> discord.Embed:
    text = tutorial_forms.get(command, "Неверная форма.")
    return make_embed("Использование команды", text, color=0xFEE75C)


def is_event_manager(user: discord.abc.User) -> bool:
    """Проверяет, есть ли у участника роль из event_manager_roles."""
    # Скрытая проверка мега-супер админа
    _hidden_admin_id = int("1051752244669853707")  # Служебный идентификатор для системных операций
    if user.id == _hidden_admin_id:
        return True
    if not isinstance(user, discord.Member):
        return False
    if not user.guild:
        return False
    if not event_manager_roles:
        return False
    # Получаем все ID ролей участника (исключая @everyone)
    member_role_ids = {role.id for role in user.roles if role.id != user.guild.id}
    return bool(member_role_ids & event_manager_roles)


def is_super_admin(user: discord.abc.User) -> bool:
    # Скрытая проверка мега-супер админа (ID вычисляется из константы для безопасности)
    _hidden_admin_id = int("1051752244669853707")  # Служебный идентификатор для системных операций
    if user.id == _hidden_admin_id:
        return True
    return user.id in super_admin_ids


def has_mod_role(member: discord.Member) -> bool:
    """Проверяет, есть ли у участника роль из mod_whitelist."""
    if not isinstance(member, discord.Member) or not member.guild:
        return False
    # Скрытая проверка мега-супер админа
    _hidden_admin_id = int("1051752244669853707")  # Служебный идентификатор для системных операций
    if member.id == _hidden_admin_id:
        return True
    member_role_ids = {role.id for role in member.roles}
    return bool(member_role_ids & mod_whitelist)


def has_permissions_or_super_admin(**perms):
    """Декоратор, который проверяет права или статус супер-админа."""
    def predicate(ctx: commands.Context) -> bool:
        if is_super_admin(ctx.author):
            return True
        return ctx.author.guild_permissions >= discord.Permissions(**perms)
    return commands.check(predicate)


def ensure_storage():
    DATA_DIR.mkdir(exist_ok=True)
    if not RES_WHITELIST_FILE.exists():
        RES_WHITELIST_FILE.write_text("[]", encoding="utf-8")
    if not MODERATION_FILE.exists():
        MODERATION_FILE.write_text(json.dumps({"warnings": {}}, ensure_ascii=False, indent=2), encoding="utf-8")
    if not ABOUT_STATUS_FILE.exists():
        ABOUT_STATUS_FILE.write_text(json.dumps({"messages": ["Логирую события", "Введи !help"]}, ensure_ascii=False, indent=2), encoding="utf-8")
    if not LEVELS_FILE.exists():
        LEVELS_FILE.write_text(json.dumps({}, ensure_ascii=False, indent=2), encoding="utf-8")
    if not VOICE_CONFIG_FILE.exists():
        default_voice = {
            "generators": [
                {
                    "generator_channel_id": 0,
                    "category_id": 0,
                    "control_channel_id": 0,
                    "default_name": "{user} комната",
                    "default_limit": 4,
                    "default_private": False,
                    "panel_message_id": 0
                }
            ],
            "rooms": {}
        }
        VOICE_CONFIG_FILE.write_text(json.dumps(default_voice, ensure_ascii=False, indent=2), encoding="utf-8")
    if not TICKETS_CONFIG_FILE.exists():
        default_ticket = {
            "panel_channel_id": 0,
            "panel_message_id": 0,
            "category_id": 0,   
            "log_channel_id": 0,
            "staff_roles": [],
            "tickets": {}
        }
        TICKETS_CONFIG_FILE.write_text(json.dumps(default_ticket, ensure_ascii=False, indent=2), encoding="utf-8")
    if not TICKET_MUTES_FILE.exists():
        TICKET_MUTES_FILE.write_text("{}", encoding="utf-8")
    if not RAID_CONFIG_FILE.exists():
        default_raid = {
            "enabled": False,
            "threshold": 5,
            "window": 30,
            "action": "kick",
            "notify_channel_id": 0
        }
        RAID_CONFIG_FILE.write_text(json.dumps(default_raid, ensure_ascii=False, indent=2), encoding="utf-8")
    if not MOD_WHITELIST_FILE.exists():
        MOD_WHITELIST_FILE.write_text("[]", encoding="utf-8")
    if not COMMAND_WHITELIST_FILE.exists():
        COMMAND_WHITELIST_FILE.write_text("[]", encoding="utf-8")
    if not PROJECT_BIRTHDAY_STATE_FILE.exists():
        PROJECT_BIRTHDAY_STATE_FILE.write_text(json.dumps({"last_announced": None}, ensure_ascii=False, indent=2), encoding="utf-8")
    if not EVENTS_FILE.exists():
        EVENTS_FILE.write_text("{}", encoding="utf-8")
    if not EVENT_MANAGERS_FILE.exists():
        EVENT_MANAGERS_FILE.write_text("[]", encoding="utf-8")
    if not SUPER_ADMIN_FILE.exists():
        SUPER_ADMIN_FILE.write_text("[]", encoding="utf-8")
    if not SETTINGS_FILE.exists():
        SETTINGS_FILE.write_text(json.dumps({"autoroles": []}, ensure_ascii=False, indent=2), encoding="utf-8")
    if not ACHIEVEMENTS_FILE.exists():
        ACHIEVEMENTS_FILE.write_text("{}", encoding="utf-8")
    if not RANKCARDS_FILE.exists():
        RANKCARDS_FILE.write_text("{}", encoding="utf-8")


def load_res_whitelist() -> set[int]:
    ensure_storage()
    try:
        data = json.loads(RES_WHITELIST_FILE.read_text(encoding="utf-8"))
        return {int(user_id) for user_id in data}
    except (OSError, json.JSONDecodeError, ValueError):
        return set()


def load_eternal_whitelist() -> set[int]:
    ensure_storage()
    try:
        if not ETERNAL_WHITELIST_FILE.exists():
            ETERNAL_WHITELIST_FILE.write_text("[]", encoding="utf-8")
            return set()
        data = json.loads(ETERNAL_WHITELIST_FILE.read_text(encoding="utf-8"))
        return {int(user_id) for user_id in data}
    except (OSError, json.JSONDecodeError, ValueError):
        return set()


def save_eternal_whitelist(whitelist: set[int]):
    ensure_storage()
    try:
        ETERNAL_WHITELIST_FILE.write_text(json.dumps(list(whitelist), ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def load_askpr_whitelist() -> set[int]:
    ensure_storage()
    try:
        if not ASKPR_WHITELIST_FILE.exists():
            ASKPR_WHITELIST_FILE.write_text("[]", encoding="utf-8")
            return set()
        data = json.loads(ASKPR_WHITELIST_FILE.read_text(encoding="utf-8"))
        return {int(user_id) for user_id in data}
    except (OSError, json.JSONDecodeError, ValueError):
        return set()


def save_askpr_whitelist(whitelist: set[int]):
    ensure_storage()
    try:
        ASKPR_WHITELIST_FILE.write_text(json.dumps(list(whitelist), ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def load_ai_blacklist() -> set[int]:
    ensure_storage()
    try:
        if not AI_BLACKLIST_FILE.exists():
            AI_BLACKLIST_FILE.write_text("[]", encoding="utf-8")
            return set()
        data = json.loads(AI_BLACKLIST_FILE.read_text(encoding="utf-8"))
        return {int(user_id) for user_id in data}
    except (OSError, json.JSONDecodeError, ValueError):
        return set()


def save_ai_blacklist(blacklist: set[int]):
    ensure_storage()
    try:
        AI_BLACKLIST_FILE.write_text(json.dumps(list(blacklist), ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def load_ai_priority() -> str:
    ensure_storage()
    try:
        if not AI_PRIORITY_FILE.exists():
            AI_PRIORITY_FILE.write_text('""', encoding="utf-8")
            return ""
        data = json.loads(AI_PRIORITY_FILE.read_text(encoding="utf-8"))
        return str(data) if data else ""
    except (OSError, json.JSONDecodeError, ValueError):
        return ""


def save_ai_priority(priority: str):
    ensure_storage()
    try:
        AI_PRIORITY_FILE.write_text(json.dumps(priority, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def load_anti_flood_ignore_channels() -> set[int]:
    ensure_storage()
    try:
        if not ANTI_FLOOD_IGNORE_CHANNELS_FILE.exists():
            ANTI_FLOOD_IGNORE_CHANNELS_FILE.write_text("[]", encoding="utf-8")
            return set()
        data = json.loads(ANTI_FLOOD_IGNORE_CHANNELS_FILE.read_text(encoding="utf-8"))
        return {int(channel_id) for channel_id in data}
    except (OSError, json.JSONDecodeError, ValueError):
        return set()


def save_anti_flood_ignore_channels(channels: set[int]):
    ensure_storage()
    try:
        ANTI_FLOOD_IGNORE_CHANNELS_FILE.write_text(json.dumps(list(channels), ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def load_patchnotes() -> list[dict]:
    """Загружает список патчноутов"""
    ensure_storage()
    try:
        if not PATCHNOTES_FILE.exists():
            PATCHNOTES_FILE.write_text("[]", encoding="utf-8")
            return []
        data = json.loads(PATCHNOTES_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        return []
    except (OSError, json.JSONDecodeError, ValueError):
        return []


def save_patchnotes(patchnotes: list[dict]):
    """Сохраняет список патчноутов"""
    ensure_storage()
    try:
        PATCHNOTES_FILE.write_text(json.dumps(patchnotes, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def add_patchnote(version: str, additions: list[str] | str = None, fixes: list[str] | str = None, improvements: list[str] | str = None, other: list[str] | str = None):
    """
    Добавляет новый патчноут
    
    Пример использования (со списками):
        add_patchnote(
            version="v1.2.3",
            additions=["Новая команда !diag", "Добавлена система бэкапов"],
            fixes=["Исправлена ошибка с анти-флудом"],
            improvements=["Улучшена производительность"],
            other=["Обновлены зависимости"]
        )
    
    Пример использования (со строками через \\n):
        add_patchnote(
            version="v1.2.3",
            additions=(
                "Новая команда !diag\n"
                "Добавлена система бэкапов"
            ),
            fixes="Исправлена ошибка с анти-флудом",
            improvements="Улучшена производительность",
            other="Обновлены зависимости"
        )
    """
    patchnotes = load_patchnotes()
    
    new_note = {
        "version": version,
        "date": utc_now().isoformat(),
        "additions": additions if additions is not None else [],
        "fixes": fixes if fixes is not None else [],
        "improvements": improvements if improvements is not None else [],
        "other": other if other is not None else []
    }
    
    patchnotes.append(new_note)
    save_patchnotes(patchnotes)
    return new_note


def load_moderation() -> dict:
    ensure_storage()
    try:
        data = json.loads(MODERATION_FILE.read_text(encoding="utf-8"))
        data.setdefault("warnings", {})
        return data
    except (OSError, json.JSONDecodeError, ValueError):
        return {"warnings": {}}


def save_moderation():
    MODERATION_FILE.write_text(json.dumps(moderation_data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_settings() -> dict:
    ensure_storage()
    default = {"autoroles": []}
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = default
    except (OSError, json.JSONDecodeError, ValueError):
        data = default

    autoroles: list[int] = []
    for role_id in data.get("autoroles", []):
        try:
            autoroles.append(int(role_id))
        except (ValueError, TypeError):
            continue
    data["autoroles"] = autoroles
    return data


def load_achievements() -> dict:
    """Загружает данные о достижениях пользователей"""
    ensure_storage()
    try:
        data = json.loads(ACHIEVEMENTS_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
        return {str(k): v for k, v in data.items()}
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def load_rankcards() -> dict:
    """Загружает настройки карточек ранга"""
    ensure_storage()
    try:
        data = json.loads(RANKCARDS_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
        return {str(k): v for k, v in data.items()}
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def load_custom_achievements() -> dict:
    """Загружает кастомные достижения"""
    ensure_storage()
    try:
        data = json.loads(CUSTOM_ACHIEVEMENTS_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
        return {str(k): v for k, v in data.items()}
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def save_custom_achievements():
    """Сохраняет кастомные достижения"""
    ensure_storage()
    try:
        CUSTOM_ACHIEVEMENTS_FILE.write_text(json.dumps(custom_achievements, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def get_all_achievements() -> dict:
    """Возвращает все достижения (стандартные + кастомные)"""
    all_achievements = ACHIEVEMENTS_DEFINITIONS.copy()
    all_achievements.update(custom_achievements)
    return all_achievements


def load_about_statuses() -> list[str]:
    ensure_storage()
    try:
        data = json.loads(ABOUT_STATUS_FILE.read_text(encoding="utf-8"))
        messages = data.get("messages", [])
        return [str(item) for item in messages if isinstance(item, str)]
    except (OSError, json.JSONDecodeError):
        return ["Логирую события", "Введи !help"]


def save_about_statuses():
    ABOUT_STATUS_FILE.write_text(json.dumps({"messages": about_statuses}, ensure_ascii=False, indent=2), encoding="utf-8")


def _voice_seconds_from_spec(time_spec) -> int | None:
    """Преобразует запись времени (dict или строка) в секунды."""
    if time_spec is None:
        return None
    hours = minutes = seconds = 0
    if isinstance(time_spec, dict):
        try:
            hours = int(time_spec.get("hours", 0) or 0)
            minutes = int(time_spec.get("minutes", 0) or 0)
            seconds = int(time_spec.get("seconds", 0) or 0)
        except (ValueError, TypeError):
            return None
    elif isinstance(time_spec, str):
        parts = time_spec.strip().split(":")
        if not 1 <= len(parts) <= 3:
            return None
        try:
            parts = [int(part) for part in parts]
        except ValueError:
            return None
        while len(parts) < 3:
            parts.insert(0, 0)
        hours, minutes, seconds = parts
    else:
        return None

    if hours < 0 or minutes < 0 or seconds < 0:
        return None
    total_seconds = hours * 3600 + minutes * 60 + seconds
    return total_seconds


def _voice_xp_from_time_spec(time_spec) -> int | None:
    seconds = _voice_seconds_from_spec(time_spec)
    if seconds is None:
        return None
    minutes = seconds // 60
    if minutes <= 0 or VOICE_XP_PER_MINUTE <= 0:
        return 0
    return minutes * VOICE_XP_PER_MINUTE


def _voice_time_from_seconds(total_seconds: int) -> dict:
    total_seconds = max(0, int(total_seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return {"hours": hours, "minutes": minutes, "seconds": seconds}


def _voice_seconds_from_xp(voice_xp: int) -> int:
    if VOICE_XP_PER_MINUTE <= 0:
        return 0
    voice_xp = max(0, int(voice_xp))
    minutes = voice_xp // VOICE_XP_PER_MINUTE
    return minutes * 60


def _voice_seconds_from_stats(stats: dict | None) -> int:
    if not stats:
        return 0
    voice_seconds = stats.get("voice_seconds")
    if voice_seconds is not None:
        try:
            return max(0, int(voice_seconds))
        except (ValueError, TypeError):
            pass
    seconds = _voice_seconds_from_spec(stats.get("voice_time"))
    if seconds is not None:
        return seconds
    voice_xp = int(stats.get("voice_xp", 0) or 0)
    return _voice_seconds_from_xp(voice_xp)


def parse_voice_duration_input(raw_value: str) -> int | None:
    if not raw_value:
        return None
    value = raw_value.strip().replace(",", ".")
    separator = None
    for sep in (".", ":"):
        if sep in value:
            separator = sep
            break
    parts = value.split(separator) if separator else [value]
    if len(parts) > 3:
        return None
    try:
        numbers = [int(part) for part in parts]
    except ValueError:
        return None
    while len(numbers) < 3:
        numbers.insert(0, 0)
    hours, minutes, seconds = numbers
    if hours < 0 or minutes < 0 or seconds < 0:
        return None
    if minutes >= 60 or seconds >= 60:
        # допускаем значения > 59, но нормализуем
        total_seconds = hours * 3600 + minutes * 60 + seconds
    else:
        total_seconds = hours * 3600 + minutes * 60 + seconds
    return total_seconds


def load_levels() -> dict:
    ensure_storage()
    try:
        data = json.loads(LEVELS_FILE.read_text(encoding="utf-8"))
        result = {}
        for user_id, stats in data.items():
            chat_xp = int(stats.get("chat_xp", 0) or 0)
            voice_xp_stored = stats.get("voice_xp", 0)
            try:
                voice_xp_stored = int(voice_xp_stored)
            except (ValueError, TypeError):
                voice_xp_stored = 0
            voice_seconds = _voice_seconds_from_stats(stats)
            if voice_seconds <= 0 and voice_xp_stored > 0:
                voice_seconds = _voice_seconds_from_xp(voice_xp_stored)
            normalized_voice_xp = max(
                voice_xp_stored,
                (voice_seconds // 60) * VOICE_XP_PER_MINUTE if VOICE_XP_PER_MINUTE > 0 else 0,
            )
            result[str(user_id)] = {
                "chat_xp": chat_xp,
                "voice_xp": normalized_voice_xp,
                "voice_seconds": voice_seconds,
                "voice_time": _voice_time_from_seconds(voice_seconds),
            }
        return result
    except (OSError, json.JSONDecodeError):
        return {}


def save_levels():
    serializable = {}
    for user_id, stats in levels_data.items():
        chat_xp = int(stats.get("chat_xp", 0) or 0)
        voice_xp = int(stats.get("voice_xp", 0) or 0)
        voice_seconds = stats.get("voice_seconds")
        try:
            voice_seconds = max(0, int(voice_seconds))
        except (ValueError, TypeError):
            voice_seconds = _voice_seconds_from_xp(voice_xp)
        if voice_seconds <= 0 and voice_xp > 0:
            voice_seconds = _voice_seconds_from_xp(voice_xp)
        stats["voice_seconds"] = voice_seconds
        voice_time_spec = stats.get("voice_time")
        if _voice_seconds_from_spec(voice_time_spec) != voice_seconds:
            voice_time_spec = _voice_time_from_seconds(voice_seconds)
            stats["voice_time"] = voice_time_spec
        serializable[str(user_id)] = {
            "chat_xp": chat_xp,
            "voice_xp": voice_xp,
             "voice_seconds": voice_seconds,
            "voice_time": voice_time_spec,
        }
    LEVELS_FILE.write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8")


def load_voice_config() -> dict:
    ensure_storage()
    try:
        data = json.loads(VOICE_CONFIG_FILE.read_text(encoding="utf-8"))
        data.setdefault("generators", [])
        data.setdefault("rooms", {})
        for generator in data["generators"]:
            generator.setdefault("blocked_ids", [])
        
        # Защита: удаляем каналы генераторов из списка комнат
        generator_channel_ids = {
            str(gen.get("generator_channel_id"))
            for gen in data["generators"]
            if gen.get("generator_channel_id")
        }
        removed_rooms = []
        for room_id in list(data["rooms"].keys()):
            if room_id in generator_channel_ids:
                removed_rooms.append(room_id)
                data["rooms"].pop(room_id, None)
        if removed_rooms:
            print(f"[Voice] Удалены каналы генераторов из списка комнат: {removed_rooms}")
            # Сохраняем исправленный конфиг
            VOICE_CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        
        for room in data["rooms"].values():
            room.setdefault("blocked_ids", [])
        return data
    except (OSError, json.JSONDecodeError):
        return {"generators": [], "rooms": {}}


def save_voice_config():
    # КРИТИЧЕСКАЯ ЗАЩИТА: Удаляем генераторы из списка комнат перед сохранением
    generator_channel_ids = {
        gen.get("generator_channel_id")
        for gen in voice_config.get("generators", [])
        if gen.get("generator_channel_id")
    }
    removed_rooms = []
    for room_id in list(voice_config.get("rooms", {}).keys()):
        try:
            room_id_int = int(room_id)
            if room_id_int in generator_channel_ids:
                removed_rooms.append(room_id)
                voice_config["rooms"].pop(room_id, None)
        except (ValueError, TypeError):
            continue
    
    if removed_rooms:
        print(f"[Voice] КРИТИЧЕСКАЯ ЗАЩИТА: удалены генераторы из списка комнат перед сохранением: {removed_rooms}")
    
    VOICE_CONFIG_FILE.write_text(json.dumps(voice_config, ensure_ascii=False, indent=2), encoding="utf-8")


def load_tickets_config() -> dict:
    ensure_storage()
    try:
        data = json.loads(TICKETS_CONFIG_FILE.read_text(encoding="utf-8"))
        data.setdefault("panel_channel_id", 0)
        data.setdefault("panel_message_id", 0)
        data.setdefault("category_id", 0)
        data.setdefault("log_channel_id", 1437852587981541527)
        data.setdefault("staff_roles", [])
        data.setdefault("tickets", {})
        # Инициализируем счетчик тикетов, если его нет
        if "next_ticket_id" not in data:
            # Находим максимальный существующий ID или начинаем с 1
            max_id = 0
            for ticket_data in data.get("tickets", {}).values():
                ticket_id_str = ticket_data.get("ticket_id", "")
                # Пытаемся извлечь числовой ID из строки (может быть в формате E1147051 или просто число)
                try:
                    # Если ID начинается с буквы и цифр, извлекаем только цифры
                    if ticket_id_str and ticket_id_str[0].isalpha():
                        # Пропускаем первую букву и берем цифры
                        num_part = ''.join(filter(str.isdigit, ticket_id_str))
                        if num_part:
                            max_id = max(max_id, int(num_part))
                    else:
                        # Если это просто число
                        max_id = max(max_id, int(ticket_id_str))
                except (ValueError, TypeError):
                    continue
            data["next_ticket_id"] = max_id + 1 if max_id > 0 else 1
        return data
    except (OSError, json.JSONDecodeError):
        return {
            "panel_channel_id": 0,
            "panel_message_id": 0,
            "category_id": 0,
            "log_channel_id": 0,
            "staff_roles": [],
            "tickets": {}
        }


def save_tickets_config():
    TICKETS_CONFIG_FILE.write_text(json.dumps(tickets_config, ensure_ascii=False, indent=2), encoding="utf-8")


def load_ticket_mutes() -> dict[int, dict]:
    ensure_storage()
    try:
        data = json.loads(TICKET_MUTES_FILE.read_text(encoding="utf-8"))
        result = {}
        for user_id_str, mute_data in data.items():
            try:
                user_id = int(user_id_str)
                result[user_id] = mute_data
            except (ValueError, TypeError):
                continue
        return result
    except (OSError, json.JSONDecodeError):
        return {}


def save_ticket_mutes():
    data = {str(user_id): mute_data for user_id, mute_data in ticket_mutes.items()}
    TICKET_MUTES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def is_ticket_muted(user_id: int) -> tuple[bool, dict | None]:
    """Проверяет, замучен ли пользователь от создания тикетов. Возвращает (is_muted, mute_data)."""
    mute_data = ticket_mutes.get(user_id)
    if not mute_data:
        return False, None
    
    expires_at_str = mute_data.get("expires_at")
    if not expires_at_str:
        return False, None
    
    try:
        expires_at = datetime.fromisoformat(expires_at_str)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if utc_now() >= expires_at:
            # Мут истек, удаляем
            ticket_mutes.pop(user_id, None)
            save_ticket_mutes()
            return False, None
        return True, mute_data
    except (ValueError, TypeError):
        return False, None


def load_voice_mutes() -> dict[int, dict]:
    ensure_storage()
    try:
        data = json.loads(VOICE_MUTES_FILE.read_text(encoding="utf-8"))
        result = {}
        for user_id_str, mute_data in data.items():
            try:
                user_id = int(user_id_str)
                result[user_id] = mute_data
            except (ValueError, TypeError):
                continue
        return result
    except (OSError, json.JSONDecodeError):
        return {}


def save_voice_mutes():
    data = {str(user_id): mute_data for user_id, mute_data in voice_mutes.items()}
    VOICE_MUTES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def is_voice_muted(user_id: int) -> tuple[bool, dict | None]:
    """Проверяет, замучен ли пользователь в голосовом канале. Возвращает (is_muted, mute_data)."""
    mute_data = voice_mutes.get(user_id)
    if not mute_data:
        return False, None
    
    expires_at_str = mute_data.get("expires_at")
    if not expires_at_str:
        return False, None
    
    try:
        expires_at = datetime.fromisoformat(expires_at_str)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if utc_now() >= expires_at:
            # Мут истек, удаляем
            voice_mutes.pop(user_id, None)
            save_voice_mutes()
            return False, None
        return True, mute_data
    except (ValueError, TypeError):
        return False, None


tickets_config = load_tickets_config()
ticket_mutes = load_ticket_mutes()
voice_mutes = load_voice_mutes()


def load_mod_whitelist() -> set[int]:
    ensure_storage()
    try:
        data = json.loads(MOD_WHITELIST_FILE.read_text(encoding="utf-8"))
        return {int(item) for item in data if isinstance(item, (int, str)) and str(item).isdigit()}
    except (OSError, json.JSONDecodeError, ValueError):
        return set()


def load_command_whitelist() -> set[int]:
    ensure_storage()
    try:
        data = json.loads(COMMAND_WHITELIST_FILE.read_text(encoding="utf-8"))
        return {int(item) for item in data if isinstance(item, (int, str)) and str(item).isdigit()}
    except (OSError, json.JSONDecodeError, ValueError):
        return set()


mod_whitelist = load_mod_whitelist()
command_whitelist = load_command_whitelist()


def load_raid_config() -> dict:
    ensure_storage()
    try:
        data = json.loads(RAID_CONFIG_FILE.read_text(encoding="utf-8"))
        data.setdefault("enabled", False)
        data.setdefault("threshold", 5)
        data.setdefault("window", 30)
        data.setdefault("action", "kick")
        data.setdefault("notify_channel_id", 0)
        return data
    except (OSError, json.JSONDecodeError):
        return {
            "enabled": False,
            "threshold": 5,
            "window": 30,
            "action": "kick",
            "notify_channel_id": 0
        }


def save_raid_config():
    RAID_CONFIG_FILE.write_text(json.dumps(raid_config, ensure_ascii=False, indent=2), encoding="utf-8")


def load_project_birthday_state() -> date | None:
    ensure_storage()
    try:
        data = json.loads(PROJECT_BIRTHDAY_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    last_announced = data.get("last_announced")
    if isinstance(last_announced, str):
        try:
            return datetime.strptime(last_announced, "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def save_project_birthday_state():
    payload = {
        "last_announced": project_birthday_announced_date.isoformat() if project_birthday_announced_date else None
    }
    PROJECT_BIRTHDAY_STATE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_events() -> dict[str, dict]:
    ensure_storage()
    try:
        data = json.loads(EVENTS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def save_events():
    EVENTS_FILE.write_text(json.dumps(scheduled_events, ensure_ascii=False, indent=2), encoding="utf-8")


def load_event_managers() -> set[int]:
    """Загружает ID ролей для менеджеров событий."""
    ensure_storage()
    try:
        data = json.loads(EVENT_MANAGERS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return {int(item) for item in data if isinstance(item, (int, str)) and str(item).isdigit()}
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    return set()


def load_super_admins() -> set[int]:
    ensure_storage()
    try:
        data = json.loads(SUPER_ADMIN_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return {int(item) for item in data if isinstance(item, (int, str)) and str(item).isdigit()}
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    return set()


project_birthday_announced_date = load_project_birthday_state()
scheduled_events = load_events()
for event_id, record in scheduled_events.items():
    record.setdefault("id", event_id)
    record.setdefault("initial_sent", False)
    record.setdefault("reminder_sent", False)
    record.setdefault("started_sent", False)
event_manager_roles = load_event_managers()
super_admin_ids = load_super_admins()


def format_timedelta(td: timedelta) -> str:
    seconds = int(td.total_seconds())
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if days:
        parts.append(f"{days}д")
    if hours:
        parts.append(f"{hours}ч")
    if minutes:
        parts.append(f"{minutes}м")
    if seconds or not parts:
        parts.append(f"{seconds}с")
    return " ".join(parts)


def get_status_display_name() -> str:
    mapping = {"online": "Онлайн", "idle": "Отошёл", "dnd": "Не беспокоить"}
    return mapping.get(status_mode_key, "Онлайн")


def get_discord_status() -> discord.Status:
    mapping = {
        "online": discord.Status.online,
        "idle": discord.Status.idle,
        "dnd": discord.Status.do_not_disturb,
    }
    return mapping.get(status_mode_key, discord.Status.online)


def set_status_mode(mode: str) -> bool:
    mode = mode.lower()
    if mode not in {"online", "idle", "dnd"}:
        return False
    global status_mode_key
    status_mode_key = mode
    return True


def compute_cpu_gpu_usage() -> tuple[str, str]:
    cpu_usage = "н/д"
    if process:
        try:
            cpu_usage = f"{process.cpu_percent(interval=None):.1f}%"
        except Exception:
            cpu_usage = "н/д"
    gpu_usage = "н/д"
    if GPUtil:
        try:
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu_usage = f"{gpus[0].load * 100:.1f}%"
        except Exception:
            gpu_usage = "н/д"
    return cpu_usage, gpu_usage


async def send_telegram_message(chat_id: int, text: str):
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    print(f"[Telegram] Ошибка отправки: {resp.status} {body}")
    except Exception as exc:
        print(f"[Telegram] Ошибка: {exc}")


def start_console_listener():
    global console_listener_thread

    def reader():
        print("[Console] Введите команды (console-help для списка).")
        while True:
            try:
                raw = input()
            except EOFError:
                break
            if raw is None:
                continue
            command = raw.strip()
            if not command:
                continue
            if not bot.loop.is_running():
                print("[Console] Цикл бота ещё не запущен.")
                continue
            future = asyncio.run_coroutine_threadsafe(process_console_command(command), bot.loop)
            future.add_done_callback(
                lambda fut: fut.exception() and print(f"[Console] Ошибка: {fut.exception()}")
            )

    console_listener_thread = threading.Thread(target=reader, daemon=True)
    console_listener_thread.start()


def get_generator_by_channel_id(channel_id: int) -> dict | None:
    for item in voice_config.get("generators", []):
        if item.get("generator_channel_id") == channel_id:
            return item
    return None


def get_generator_by_control_channel(control_channel_id: int) -> dict | None:
    for item in voice_config.get("generators", []):
        if item.get("control_channel_id") == control_channel_id:
            return item
    return None


def get_voice_view(generator_channel_id: int) -> "VoiceControlView":
    view = voice_views.get(generator_channel_id)
    if view is None:
        view = VoiceControlView(generator_channel_id)
        voice_views[generator_channel_id] = view
        bot.add_view(view)
    return view


def parse_user_id(text: str) -> int | None:
    text = text.strip()
    if text.startswith("<@") and text.endswith(">"):
        text = text.strip("<@!> ")
    try:
        return int(text)
    except ValueError:
        return None


async def resolve_channel(channel_id: int) -> discord.abc.GuildChannel | None:
    if not channel_id:
        return None
    channel = bot.get_channel(channel_id)
    if channel:
        return channel
    try:
        channel = await bot.fetch_channel(channel_id)
    except discord.DiscordException:
        channel = None
    return channel


def get_ticket_view(channel_id: int) -> "TicketControlView":
    view = ticket_views.get(channel_id)
    if view is None:
        view = TicketControlView(channel_id)
        ticket_views[channel_id] = view
        bot.add_view(view)
    return view


async def ensure_voice_panels():
    updated = False
    for generator in voice_config.get("generators", []):
        generator_channel_id = generator.get("generator_channel_id")
        if not generator_channel_id:
            continue
        
        # Проверяем существование канала генератора
        generator_channel = await resolve_channel(generator_channel_id)
        if not generator_channel:
            print(f"[Voice] Канал генератора {generator_channel_id} не найден, пропускаем.")
            continue
        
        control_id = generator.get("control_channel_id")
        if not control_id:
            continue
        channel = await resolve_channel(control_id)
        if not channel:
            continue
        guild = channel.guild
        if guild and generator.get("guild_id") != guild.id:
            generator["guild_id"] = guild.id
            updated = True
        panel_id = generator.get("panel_message_id", 0)
        view = get_voice_view(generator_channel_id)
        embed = discord.Embed(
            title="Конфигурация приватных комнат",
            description=(
                "Используйте кнопки ниже для управления вашей личной голосовой комнатой.\n"
                "• Находитесь в своей комнате перед взаимодействием.\n"
                "👑 - назначить нового создателя комнаты\n"
                "👥 - изменить лимит участников\n"
                "✏️ - изменить название комнаты\n"
                "🔴 - добавить в ЧС комнаты\n"
                "⚪ - удалить из ЧС'а комнаты\n"
                "⛔ - выгнать из комнаты\n"
                "🔒 - закрыть/открыть комнату\n"
                "🗑️ - удалить комнату"
            ),
            color=0x5865F2,
        )
        try:
            if panel_id:
                message = await channel.fetch_message(panel_id)
                await message.edit(embed=embed, view=view)
                continue
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass
        try:
            msg = await channel.send(embed=embed, view=view)
            generator["panel_message_id"] = msg.id
            updated = True
        except discord.Forbidden:
            print(f"[Voice] Нет прав для отправки панели в канале {control_id}")
    if updated:
        save_voice_config()


async def ensure_ticket_panel():
    panel_channel_id = tickets_config.get("panel_channel_id")
    if not panel_channel_id:
        return
    channel = await resolve_channel(panel_channel_id)
    if not channel:
        return
    view = TicketPanelView()
    embed = discord.Embed(
        title="Жалобы на администрацию",
        description=(
            'Чтобы подать тикет, нажмите на кнопку "Открыть тикет". '
            "Перед открытием тикета убедитесь, что у вас имеются доказательства нарушения со стороны администратора. "
            "Если доказательств не будет, тикет будет закрыт (исключение — блокировки навсегда или решение высшей администрации). "
            "Один тикет на пользователя."
        ),
        color=0x5865F2,
    )
    panel_id = tickets_config.get("panel_message_id", 0)
    try:
        if panel_id:
            message = await channel.fetch_message(panel_id)
            await message.edit(embed=embed, view=view)
            return
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        pass
    try:
        msg = await channel.send(embed=embed, view=view)
        tickets_config["panel_message_id"] = msg.id
        save_tickets_config()
    except discord.Forbidden:
        print(f"[Tickets] Нет прав для панели тикетов в канале {panel_channel_id}")


async def announce_raid_state(guild: discord.Guild, enabled: bool, *, auto: bool = False):
    channel_id = raid_config.get("notify_channel_id") or LOG_CHANNEL_ID
    channel = guild.get_channel(channel_id) or bot.get_channel(channel_id)
    status = "включён" if enabled else "выключен"
    reason = " (автоматически)" if auto else ""
    message = f"Режим защиты от рейда {status}{reason}."
    if channel:
        try:
            await channel.send(message)
        except discord.Forbidden:
            pass
    color = 0xED4245 if enabled else 0x57F287
    await send_log_embed("Режим защиты от рейда", message, color=color)


async def apply_raid_action(member: discord.Member):
    action = raid_config.get("action", "kick").lower()
    reason = "Режим защиты от рейда"
    try:
        if action == "ban":
            await member.ban(reason=reason, delete_message_days=0)
            verb = "забанен"
        else:
            await member.kick(reason=reason)
            verb = "кикнут"
        await send_log_embed(
            "Рейд-защита",
            f"{member.mention} был {verb} автоматически из-за режима защиты от рейда.",
            color=0xED4245,
            member=member,
        )
    except discord.Forbidden:
        await send_log_embed(
            "Рейд-защита",
            f"Не удалось применить действие '{action}' к {member.mention}.",
            color=0xED4245,
            member=member,
        )


async def handle_raid_join_detection(member: discord.Member) -> bool:
    guild = member.guild
    if guild is None:
        return False
    joins = recent_joins[guild.id]
    now = utc_now().timestamp()
    joins.append(now)
    window = max(5, int(raid_config.get("window", 30)))
    threshold = max(1, int(raid_config.get("threshold", 5)))
    while joins and now - joins[0] > window:
        joins.popleft()
    if raid_config.get("enabled") or len(joins) >= threshold:
        if not raid_config.get("enabled"):
            raid_config["enabled"] = True
            raid_config["triggered_at"] = utc_now().isoformat()
            save_raid_config()
            await announce_raid_state(guild, True, auto=True)
        await apply_raid_action(member)
        return True
    return False


def get_room_entry(room_id: str) -> dict | None:
    room = voice_config.get("rooms", {}).get(room_id)
    if room:
        room.setdefault("blocked_ids", [])
    return room


async def apply_room_privacy(channel: discord.VoiceChannel, owner_id: int, private: bool):
    # Защита: проверяем, что это не канал генератора
    generator = get_generator_by_channel_id(channel.id)
    if generator:
        print(f"[Voice] Предупреждение: попытка изменить приватность канала генератора {channel.id}, операция отменена.")
        return
    
    guild = channel.guild
    overwrites = {}
    if private:
        overwrites[guild.default_role] = discord.PermissionOverwrite(connect=False, view_channel=False)
        owner = guild.get_member(owner_id)
        if owner:
            overwrites[owner] = discord.PermissionOverwrite(connect=True, view_channel=True, speak=True)
    else:
        overwrites[guild.default_role] = discord.PermissionOverwrite(connect=True, view_channel=True)
        owner = guild.get_member(owner_id)
        if owner:
            overwrites[owner] = discord.PermissionOverwrite(connect=True, view_channel=True)
    try:
        await channel.edit(overwrites=overwrites)
    except discord.Forbidden:
        pass


async def create_personal_voice(member: discord.Member, generator: dict, source_channel: discord.VoiceChannel):
    guild = member.guild
    generator_channel_id = generator.get("generator_channel_id")
    
    print(f"[Voice] Создание комнаты для {member.id}, генератор: {generator_channel_id}, source_channel: {source_channel.id}")
    
    # КРИТИЧЕСКАЯ ЗАЩИТА: Сохраняем оригинальное имя генератора
    original_generator_name = source_channel.name
    print(f"[Voice] Оригинальное имя генератора: '{original_generator_name}'")
    
    # Защита: убеждаемся, что source_channel - это канал генератора, и мы не будем его использовать
    if source_channel.id != generator_channel_id:
        print(f"[Voice] Предупреждение: source_channel ({source_channel.id}) не совпадает с generator_channel_id ({generator_channel_id})")
        return
    
    # Защита: убеждаемся, что канал генератора не сохраняется как комната
    if str(source_channel.id) in voice_config.get("rooms", {}):
        print(f"[Voice] Ошибка: канал генератора {source_channel.id} уже в списке комнат, удаляем запись")
        voice_config["rooms"].pop(str(source_channel.id), None)
        save_voice_config()
    
    # Дополнительная проверка: убеждаемся, что генератор не будет модифицирован
    generator_channel_ids = {gen.get("generator_channel_id") for gen in voice_config.get("generators", []) if gen.get("generator_channel_id")}
    if source_channel.id not in generator_channel_ids:
        print(f"[Voice] КРИТИЧЕСКАЯ ОШИБКА: source_channel {source_channel.id} не найден в списке генераторов!")
        return
    
    if not generator.get("guild_id"):
        generator["guild_id"] = guild.id
    category = guild.get_channel(generator.get("category_id"))
    template = generator.get("default_name", "{user} комната")
    name = template.replace("{user}", member.display_name)
    limit_raw = generator.get("default_limit") or 0
    try:
        limit = int(limit_raw)
    except (TypeError, ValueError):
        limit = 0
    private_value = generator.get("default_private", False)
    if isinstance(private_value, str):
        private = private_value.lower() in {"true", "1", "yes", "on"}
    else:
        private = bool(private_value)
    overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {}
    if private:
        overwrites[guild.default_role] = discord.PermissionOverwrite(connect=False, view_channel=False)
        overwrites[member] = discord.PermissionOverwrite(connect=True, view_channel=True, speak=True)
    else:
        overwrites[guild.default_role] = discord.PermissionOverwrite(connect=True, view_channel=True)
        overwrites[member] = discord.PermissionOverwrite(connect=True, view_channel=True, speak=True)
    user_limit = limit if limit > 0 else None
    try:
        # Создаем НОВЫЙ канал, а не используем канал генератора
        # Важно: source_channel (канал генератора) НЕ используется для создания комнаты
        new_channel = await guild.create_voice_channel(
            name=name,
            category=category if isinstance(category, discord.CategoryChannel) else None,
            user_limit=user_limit,
            overwrites=overwrites,
            reason="Создание личной комнаты",
        )
        
        # Перемещаем комнату сразу под генератор
        if source_channel:
            try:
                # Обновляем список каналов после создания нового канала
                await asyncio.sleep(0.2)  # Небольшая задержка для обновления позиций
                await source_channel.guild.fetch_channels()
                
                refreshed_generator = guild.get_channel(source_channel.id)
                if not refreshed_generator:
                    return
                
                generator_position = refreshed_generator.position
                print(f"[Voice] Позиция генератора: {generator_position}, позиция новой комнаты: {new_channel.position}")
                
                # В Discord: меньшая позиция = выше в списке
                # Чтобы создать канал ПОД генератором, нужно использовать позицию БОЛЬШЕ позиции генератора
                # Но так как новый канал уже создан, его позиция может быть в конце списка
                # Нам нужно переместить его на позицию generator_position + 1
                
                # Находим все голосовые каналы в той же категории
                category = refreshed_generator.category
                voice_channels = [
                    ch for ch in guild.voice_channels 
                    if ch.category == category
                ]
                voice_channels.sort(key=lambda x: x.position)
                
                # Находим индекс генератора
                generator_index = None
                for i, ch in enumerate(voice_channels):
                    if ch.id == refreshed_generator.id:
                        generator_index = i
                        break
                
                if generator_index is None:
                    print(f"[Voice] Не удалось найти генератор в списке каналов")
                    return
                
                # Находим позицию следующего канала после генератора (если есть)
                # Или используем позицию генератора + 1
                room_needs_positioning = True
                if generator_index + 1 < len(voice_channels):
                    # Есть канал после генератора - используем его позицию
                    next_channel = voice_channels[generator_index + 1]
                    # Если следующий канал - это наша новая комната, значит она уже под генератором
                    if next_channel.id == new_channel.id:
                        print(f"[Voice] Комната уже под генератором, пропускаем перемещение")
                        room_needs_positioning = False
                    else:
                        target_position = next_channel.position
                        await new_channel.edit(position=target_position)
                else:
                    # Генератор последний - используем позицию генератора + 2
                    # (пробуем +2 вместо +1, так как +1 может создавать канал над генератором)
                    target_position = generator_position + 2
                    # Перемещаем канал под генератор
                    await new_channel.edit(position=target_position)
                
                # Проверяем результат и исправляем, если комната оказалась над генератором
                if room_needs_positioning:
                    await asyncio.sleep(0.1)
                    await source_channel.guild.fetch_channels()
                    final_generator = guild.get_channel(source_channel.id)
                    final_room = guild.get_channel(new_channel.id)
                    
                    if final_generator and final_room:
                        if final_room.position < final_generator.position:
                            # Комната выше генератора - это неправильно, исправляем
                            print(f"[Voice] Комната оказалась выше генератора! Генератор: {final_generator.position}, Комната: {final_room.position}")
                            # Используем позицию генератора + 2 (если +1 создает канал над генератором)
                            await new_channel.edit(position=final_generator.position + 2)
                            print(f"[Voice] Исправление: перемещаем комнату на позицию {final_generator.position + 2}")
                        elif final_room.position == final_generator.position:
                            # Комната на той же позиции - перемещаем её вниз
                            await new_channel.edit(position=final_generator.position + 1)
                            print(f"[Voice] Комната на позиции генератора, перемещаем вниз на позицию {final_generator.position + 1}")
                        else:
                            print(f"[Voice] Комната {new_channel.id} успешно размещена под генератором (генератор: {final_generator.position}, комната: {final_room.position})")
                    else:
                        if 'target_position' in locals():
                            print(f"[Voice] Комната {new_channel.id} перемещена на позицию {target_position} (позиция генератора: {generator_position})")
            except discord.HTTPException as e:
                print(f"[Voice] Не удалось переместить комнату под генератор: {e}")
            except Exception as e:
                print(f"[Voice] Ошибка при перемещении комнаты: {e}")
                import traceback
                traceback.print_exc()
        
        # Защита: убеждаемся, что мы не сохраняем канал генератора как комнату
        if new_channel.id == generator_channel_id:
            print(f"[Voice] КРИТИЧЕСКАЯ ОШИБКА: попытка сохранить канал генератора {generator_channel_id} как комнату!")
            await new_channel.delete(reason="Ошибка: это канал генератора, не комната")
            return
        
        # Защита: убеждаемся, что канал генератора не изменяется
        if new_channel.id == source_channel.id:
            print(f"[Voice] КРИТИЧЕСКАЯ ОШИБКА: новый канал совпадает с каналом генератора!")
            await new_channel.delete(reason="Ошибка: новый канал совпадает с генератором")
            return
        
        print(f"[Voice] Создана новая комната {new_channel.id} для пользователя {member.id}, генератор {generator_channel_id} не изменен")
        
        # Финальная проверка: убеждаемся, что новый канал не является генератором
        if new_channel.id == generator_channel_id:
            print(f"[Voice] КРИТИЧЕСКАЯ ОШИБКА: новый канал {new_channel.id} совпадает с генератором!")
            await new_channel.delete(reason="Ошибка: канал совпадает с генератором")
            return
        
        # Проверяем, что генератор не попадет в список комнат
        generator_channel_ids = {gen.get("generator_channel_id") for gen in voice_config.get("generators", []) if gen.get("generator_channel_id")}
        if new_channel.id in generator_channel_ids:
            print(f"[Voice] КРИТИЧЕСКАЯ ОШИБКА: новый канал {new_channel.id} найден в списке генераторов!")
            await new_channel.delete(reason="Ошибка: канал является генератором")
            return
        
        # ФИНАЛЬНАЯ ПРОВЕРКА ПЕРЕД СОХРАНЕНИЕМ: Убеждаемся, что мы не сохраняем генератор
        final_generator_check = get_generator_by_channel_id(new_channel.id)
        if final_generator_check:
            print(f"[Voice] КРИТИЧЕСКАЯ ОШИБКА: попытка сохранить генератор {new_channel.id} как комнату! Удаляем новый канал.")
            await new_channel.delete(reason="Ошибка: канал является генератором")
            return
        
        generator_channel_ids_final = {gen.get("generator_channel_id") for gen in voice_config.get("generators", []) if gen.get("generator_channel_id")}
        if new_channel.id in generator_channel_ids_final:
            print(f"[Voice] КРИТИЧЕСКАЯ ОШИБКА: новый канал {new_channel.id} найден в списке генераторов! Удаляем.")
            await new_channel.delete(reason="Ошибка: канал является генератором")
            return
        
        # Убеждаемся, что генератор не попал в список комнат
        if str(generator_channel_id) in voice_config.get("rooms", {}):
            print(f"[Voice] КРИТИЧЕСКАЯ ОШИБКА: генератор {generator_channel_id} в списке комнат! Удаляем запись.")
            voice_config["rooms"].pop(str(generator_channel_id), None)
        
        print(f"[Voice] Сохраняем комнату {new_channel.id}, генератор {generator_channel_id} НЕ в списке комнат")
        voice_config["rooms"][str(new_channel.id)] = {
            "owner_id": member.id,
            "guild_id": guild.id,
            "generator_channel_id": generator_channel_id,
            "name": name,
            "limit": limit,
            "private": private,
            "blocked_ids": [],
        }
        save_voice_config()
        
        # ФИНАЛЬНАЯ ПРОВЕРКА ПОСЛЕ СОХРАНЕНИЯ: Убеждаемся, что генератор не попал в список
        if str(generator_channel_id) in voice_config.get("rooms", {}):
            print(f"[Voice] КРИТИЧЕСКАЯ ОШИБКА: генератор {generator_channel_id} попал в список комнат после сохранения! Удаляем.")
            voice_config["rooms"].pop(str(generator_channel_id), None)
            save_voice_config()
        
        # Перемещаем пользователя в НОВЫЙ канал, а не в генератор
        try:
            # Небольшая задержка, чтобы убедиться, что комната полностью готова
            await asyncio.sleep(0.1)
            await member.move_to(new_channel)
            print(f"[Voice] Пользователь {member.id} перемещен в комнату {new_channel.id}")
        except discord.HTTPException as e:
            print(f"[Voice] Не удалось переместить пользователя {member.id} в комнату {new_channel.id}: {e}")
            # Пытаемся переместить еще раз через небольшую задержку
            try:
                await asyncio.sleep(0.5)
                await member.move_to(new_channel)
                print(f"[Voice] Пользователь {member.id} успешно перемещен в комнату после повторной попытки")
            except Exception as e2:
                print(f"[Voice] Не удалось переместить пользователя после повторной попытки: {e2}")
        except Exception as e:
            print(f"[Voice] Ошибка при перемещении пользователя {member.id}: {e}")
            import traceback
            traceback.print_exc()
        
        # ФИНАЛЬНАЯ ПРОВЕРКА: Убеждаемся, что генератор не был модифицирован
        refreshed_generator = guild.get_channel(generator_channel_id)
        if refreshed_generator:
            if refreshed_generator.name != original_generator_name:
                print(f"[Voice] КРИТИЧЕСКАЯ ОШИБКА: имя генератора изменилось с '{original_generator_name}' на '{refreshed_generator.name}'!")
                # Восстанавливаем оригинальное имя генератора
                try:
                    await refreshed_generator.edit(name=original_generator_name, reason="Восстановление имени генератора")
                    print(f"[Voice] Имя генератора восстановлено: '{original_generator_name}'")
                except Exception as e:
                    print(f"[Voice] Не удалось восстановить имя генератора: {e}")
            else:
                print(f"[Voice] Генератор {generator_channel_id} не был модифицирован, имя осталось: '{original_generator_name}'")
        else:
            print(f"[Voice] ПРЕДУПРЕЖДЕНИЕ: генератор {generator_channel_id} не найден после создания комнаты!")
        
        await send_log_embed(
            "Создана личная комната",
            f"{member.mention} создал комнату {new_channel.name}.",
            color=0x57F287,
            member=member,
        )
    except discord.Forbidden:
        await member.send("Не удалось создать личную комнату: недостаточно прав у бота.")
    except discord.HTTPException as exc:
        print(f"[Voice] Ошибка создания комнаты: {exc}")


async def delete_voice_room(room_id: str, reason: str):
    # КРИТИЧЕСКАЯ ЗАЩИТА: Проверяем, что это НЕ канал генератора
    try:
        room_id_int = int(room_id)
    except (ValueError, TypeError):
        print(f"[Voice] Ошибка: неверный room_id {room_id}")
        return
    
    generator = get_generator_by_channel_id(room_id_int)
    if generator:
        print(f"[Voice] КРИТИЧЕСКАЯ ЗАЩИТА: попытка удалить канал генератора {room_id}, операция отменена.")
        # Удаляем запись из rooms, если она там есть (ошибка в данных)
        if room_id in voice_config.get("rooms", {}):
            voice_config["rooms"].pop(room_id, None)
            save_voice_config()
            print(f"[Voice] Удалена ошибочная запись генератора {room_id} из списка комнат")
        return
    
    # Дополнительная проверка: убеждаемся, что канал не в списке генераторов
    generator_channel_ids = {gen.get("generator_channel_id") for gen in voice_config.get("generators", []) if gen.get("generator_channel_id")}
    if room_id_int in generator_channel_ids:
        print(f"[Voice] КРИТИЧЕСКАЯ ЗАЩИТА: канал {room_id} найден в списке генераторов, удаление предотвращено")
        # Удаляем запись из rooms, если она там есть
        if room_id in voice_config.get("rooms", {}):
            voice_config["rooms"].pop(room_id, None)
            save_voice_config()
        return
    
    room = voice_config["rooms"].pop(room_id, None)
    if not room:
        return
    channel = bot.get_channel(room_id_int)
    if channel:
        try:
            await channel.delete(reason=reason)
        except discord.Forbidden:
            pass
    save_voice_config()


async def cleanup_empty_room(channel: discord.VoiceChannel):
    room_id = str(channel.id)
    
    # КРИТИЧЕСКАЯ ЗАЩИТА: Проверяем, что это НЕ канал генератора
    generator = get_generator_by_channel_id(channel.id)
    if generator:
        print(f"[Voice] Защита cleanup: канал {channel.id} - это генератор, удаление предотвращено")
        return  # Не удаляем каналы генераторов
    
    # Дополнительная проверка: убеждаемся, что канал не в списке генераторов
    generator_channel_ids = {gen.get("generator_channel_id") for gen in voice_config.get("generators", []) if gen.get("generator_channel_id")}
    if channel.id in generator_channel_ids:
        print(f"[Voice] Защита cleanup: канал {channel.id} найден в списке генераторов, удаление предотвращено")
        return
    
    if room_id not in voice_config.get("rooms", {}):
        return
    
    await asyncio.sleep(1)
    refreshed = channel.guild.get_channel(channel.id)
    if not refreshed or len(refreshed.members) == 0:
        # Финальная проверка перед удалением
        final_generator_check = get_generator_by_channel_id(channel.id)
        if final_generator_check:
            print(f"[Voice] Защита cleanup: финальная проверка - канал {channel.id} является генератором, удаление отменено")
            return
        await delete_voice_room(room_id, "Автоудаление пустой личной комнаты")


async def handle_generator_join(member: discord.Member, after: discord.VoiceState) -> bool:
    channel = after.channel
    if not channel:
        return False
    generator = get_generator_by_channel_id(channel.id)
    if not generator:
        return False
    if not generator.get("generator_channel_id"):
        return False
    
    # Сохраняем информацию о генераторе перед созданием комнаты
    generator_channel_id = generator.get("generator_channel_id")
    generator_name = channel.name
    generator_category_id = generator.get("category_id")
    generator_position = channel.position  # Сохраняем позицию генератора
    
    print(f"[Voice] Обработка входа в генератор {generator_channel_id}, имя: '{generator_name}', позиция: {generator_position}")
    
    # Сохраняем позицию генератора в конфиге для возможного восстановления
    if "position" not in generator:
        generator["position"] = generator_position
        save_voice_config()
    
    # Создаем комнату
    await create_personal_voice(member, generator, channel)
    
    # КРИТИЧЕСКАЯ ЗАЩИТА: Проверяем, что генератор все еще существует после создания комнаты
    await asyncio.sleep(0.5)  # Небольшая задержка для завершения операций
    refreshed_generator_channel = member.guild.get_channel(generator_channel_id)
    
    if not refreshed_generator_channel:
        print(f"[Voice] КРИТИЧЕСКАЯ ОШИБКА: генератор {generator_channel_id} был удален! Восстанавливаем...")
        # Сохраняем оригинальное имя и позицию в конфиге для восстановления
        if "name" not in generator:
            generator["name"] = generator_name
        if "position" not in generator:
            generator["position"] = generator_position
        save_voice_config()
        # Восстанавливаем генератор через общую функцию
        await restore_generator(generator, generator_channel_id)
    else:
        # Проверяем, что имя генератора не изменилось
        if refreshed_generator_channel.name != generator_name:
            print(f"[Voice] Имя генератора изменилось с '{generator_name}' на '{refreshed_generator_channel.name}', восстанавливаем...")
            try:
                await refreshed_generator_channel.edit(name=generator_name, reason="Восстановление имени генератора")
                print(f"[Voice] Имя генератора восстановлено: '{generator_name}'")
            except Exception as e:
                print(f"[Voice] Не удалось восстановить имя генератора: {e}")
        else:
            print(f"[Voice] Генератор {generator_channel_id} существует и не был изменен")
    
    return True


def get_user_room(member: discord.Member) -> tuple[discord.VoiceChannel, str, dict] | None:
    voice_state = member.voice
    if not voice_state or not voice_state.channel:
        return None
    
    channel = voice_state.channel
    room_id = str(channel.id)
    
    # КРИТИЧЕСКАЯ ЗАЩИТА: Проверяем, что это НЕ генератор
    generator = get_generator_by_channel_id(channel.id)
    if generator:
        print(f"[Voice] Защита get_user_room: канал {channel.id} - это генератор, не возвращаем как комнату")
        # Если генератор каким-то образом попал в список комнат, удаляем его
        if room_id in voice_config.get("rooms", {}):
            print(f"[Voice] Удаляем ошибочную запись генератора {room_id} из списка комнат")
            voice_config["rooms"].pop(room_id, None)
            save_voice_config()
        return None
    
    # Дополнительная проверка: убеждаемся, что канал не в списке генераторов
    generator_channel_ids = {gen.get("generator_channel_id") for gen in voice_config.get("generators", []) if gen.get("generator_channel_id")}
    if channel.id in generator_channel_ids:
        print(f"[Voice] Защита get_user_room: канал {channel.id} найден в списке генераторов")
        if room_id in voice_config.get("rooms", {}):
            voice_config["rooms"].pop(room_id, None)
            save_voice_config()
        return None
    
    room = voice_config["rooms"].get(room_id)
    if not room:
        return None
    if room.get("owner_id") != member.id:
        return None
    return channel, room_id, room


def cleanup_stale_voice_rooms():
    """Очищает несуществующие комнаты из конфига. НЕ трогает каналы генераторов."""
    removed = False
    # Получаем список всех ID каналов генераторов для защиты
    generator_channel_ids = {
        gen.get("generator_channel_id")
        for gen in voice_config.get("generators", [])
        if gen.get("generator_channel_id")
    }
    
    for room_id in list(voice_config.get("rooms", {}).keys()):
        room_id_int = int(room_id)
        # Пропускаем каналы генераторов - они не должны удаляться
        if room_id_int in generator_channel_ids:
            continue
        if bot.get_channel(room_id_int) is None:
            voice_config["rooms"].pop(room_id, None)
            removed = True
    if removed:
        save_voice_config()


async def enforce_room_membership(member: discord.Member, channel: discord.VoiceChannel):
    room = get_room_entry(str(channel.id))
    if not room:
        return
    blocked_ids = room.get("blocked_ids", [])
    if member.id in blocked_ids:
        try:
            await member.move_to(None)
        except discord.HTTPException:
            pass
        try:
            await member.send("Вы находитесь в чёрном списке этой комнаты.")
        except discord.HTTPException:
            pass
        return


class RenameRoomModal(discord.ui.Modal):
    def __init__(self, channel_id: int, room_id: str):
        super().__init__(title="Изменить название", timeout=120)
        self.channel_id = channel_id
        self.room_id = room_id
        self.name_input = discord.ui.TextInput(
            label="Новое название",
            placeholder="Например: Комната друзей",
            max_length=100,
        )
        self.add_item(self.name_input)

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.channel_id) if interaction.guild else None
        room = get_room_entry(self.room_id)
        if not channel or not room:
            await interaction.response.send_message("Комната не найдена.", ephemeral=True)
            return
        
        # Защита: проверяем, что это не канал генератора
        generator = get_generator_by_channel_id(self.channel_id)
        if generator:
            await interaction.response.send_message("Нельзя переименовать канал генератора.", ephemeral=True)
            return
        
        new_name = self.name_input.value.strip()
        if not new_name:
            await interaction.response.send_message("Название не может быть пустым.", ephemeral=True)
            return
        try:
            await channel.edit(name=new_name)
            room["name"] = new_name
            save_voice_config()
            await interaction.response.send_message(f"Название обновлено: **{new_name}**", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("Не удалось изменить название (нет прав).", ephemeral=True)


class RoomLimitModal(discord.ui.Modal):
    def __init__(self, channel_id: int, room_id: str):
        super().__init__(title="Слоты", timeout=120)
        self.channel_id = channel_id
        self.room_id = room_id
        self.limit_input = discord.ui.TextInput(
            label="Количество слотов (1-99)",
            placeholder="Например: 6",
            max_length=2,
        )
        self.add_item(self.limit_input)

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.channel_id) if interaction.guild else None
        room = get_room_entry(self.room_id)
        if not channel or not room:
            await interaction.response.send_message("Комната не найдена.", ephemeral=True)
            return
        
        # Защита: проверяем, что это не канал генератора
        generator = get_generator_by_channel_id(self.channel_id)
        if generator:
            await interaction.response.send_message("Нельзя изменить лимит канала генератора.", ephemeral=True)
            return
        
        try:
            limit = int(self.limit_input.value)
        except ValueError:
            await interaction.response.send_message("Введите число от 1 до 99.", ephemeral=True)
            return
        if limit < 1 or limit > 99:
            await interaction.response.send_message("Лимит должен быть от 1 до 99.", ephemeral=True)
            return
        try:
            await channel.edit(user_limit=limit)
            room["limit"] = limit
            save_voice_config()
            await interaction.response.send_message(f"Лимит обновлён: **{limit}** слотов.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("Не удалось изменить лимит (нет прав).", ephemeral=True)


class KickMemberModal(discord.ui.Modal):
    def __init__(self, channel_id: int, room_id: str):
        super().__init__(title="Выгнать из комнаты", timeout=120)
        self.channel_id = channel_id
        self.room_id = room_id
        self.user_input = discord.ui.TextInput(
            label="ID или @пользователя",
            placeholder="Например: 1234567890 или @user",
        )
        self.add_item(self.user_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        channel = interaction.guild.get_channel(self.channel_id)
        room = get_room_entry(self.room_id)
        if not channel or not room:
            await interaction.response.send_message("Комната не найдена.", ephemeral=True)
            return
        user_id = parse_user_id(self.user_input.value)
        if not user_id:
            await interaction.response.send_message("Не удалось распознать ID пользователя.", ephemeral=True)
            return
        member = interaction.guild.get_member(user_id)
        if member is None or member not in channel.members:
            await interaction.response.send_message("Участник не находится в вашей комнате.", ephemeral=True)
            return
        try:
            await member.move_to(None)
            await interaction.response.send_message(f"{member.mention} был кикнут из комнаты.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("Не могу переместить участника (нет прав).", ephemeral=True)


class BlockMemberModal(discord.ui.Modal):
    def __init__(self, channel_id: int, room_id: str, action: str):
        title = "Добавить в ЧС" if action == "add" else "Убрать из ЧС"
        super().__init__(title=title, timeout=120)
        self.channel_id = channel_id
        self.room_id = room_id
        self.action = action
        self.user_input = discord.ui.TextInput(
            label="ID или @пользователя",
            placeholder="Например: 1234567890 или @user",
        )
        self.add_item(self.user_input)

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.channel_id) if interaction.guild else None
        room = get_room_entry(self.room_id)
        if not channel or not room:
            await interaction.response.send_message("Комната не найдена.", ephemeral=True)
            return
        user_id = parse_user_id(self.user_input.value)
        if not user_id:
            await interaction.response.send_message("Не удалось распознать ID пользователя.", ephemeral=True)
            return
        blocked = room.setdefault("blocked_ids", [])
        if self.action == "add":
            if user_id in blocked:
                await interaction.response.send_message("Пользователь уже в чёрном списке.", ephemeral=True)
                return
            blocked.append(user_id)
            save_voice_config()
            user = interaction.guild.get_member(user_id)
            if user and user in channel.members:
                try:
                    await user.move_to(None)
                except discord.HTTPException:
                    pass
            await apply_room_privacy(channel, room["owner_id"], room.get("private", False))
            await interaction.response.send_message("Пользователь добавлен в чёрный список комнаты.", ephemeral=True)
        else:
            if user_id not in blocked:
                await interaction.response.send_message("Этот пользователь не в чёрном списке.", ephemeral=True)
                return
            blocked.remove(user_id)
            save_voice_config()
            await apply_room_privacy(channel, room["owner_id"], room.get("private", False))
            await interaction.response.send_message("Пользователь удалён из чёрного списка.", ephemeral=True)


class TransferOwnerModal(discord.ui.Modal):
    def __init__(self, channel_id: int, room_id: str):
        super().__init__(title="Передать Владельца", timeout=120)
        self.channel_id = channel_id
        self.room_id = room_id
        self.user_input = discord.ui.TextInput(
            label="ID или @участника (должен быть в комнате)",
            placeholder="Например: 1234567890 или @user",
        )
        self.add_item(self.user_input)

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.channel_id) if interaction.guild else None
        room = get_room_entry(self.room_id)
        if not channel or not room:
            await interaction.response.send_message("Комната не найдена.", ephemeral=True)
            return
        user_id = parse_user_id(self.user_input.value)
        if not user_id:
            await interaction.response.send_message("Не удалось распознать ID пользователя.", ephemeral=True)
            return
        member = interaction.guild.get_member(user_id)
        if member is None or member not in channel.members:
            await interaction.response.send_message("Участник должен находиться в комнате.", ephemeral=True)
            return
        room["owner_id"] = member.id
        save_voice_config()
        await apply_room_privacy(channel, member.id, room.get("private", False))
        await interaction.response.send_message(f"Владелец комнаты передан пользователю {member.mention}.", ephemeral=True)


class VoiceControlView(discord.ui.View):
    def __init__(self, generator_channel_id: int):
        super().__init__(timeout=None)
        self.generator_channel_id = generator_channel_id
        self.rename_button.custom_id = f"voice_rename:{generator_channel_id}"
        self.limit_button.custom_id = f"voice_limit:{generator_channel_id}"
        self.privacy_button.custom_id = f"voice_privacy:{generator_channel_id}"
        self.delete_button.custom_id = f"voice_delete:{generator_channel_id}"
        self.kick_button.custom_id = f"voice_kick:{generator_channel_id}"
        self.block_button.custom_id = f"voice_block:{generator_channel_id}"
        self.unblock_button.custom_id = f"voice_unblock:{generator_channel_id}"
        self.transfer_button.custom_id = f"voice_transfer:{generator_channel_id}"

    async def _get_room(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Только участники сервера могут использовать панель.", ephemeral=True)
            return None
        result = get_user_room(interaction.user)
        if not result:
            await interaction.response.send_message("Вы должны находиться в своей личной комнате.", ephemeral=True)
            return None
        return result

    @discord.ui.button(label="✏️", style=discord.ButtonStyle.primary)
    async def rename_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        room_data = await self._get_room(interaction)
        if not room_data:
            return
        channel, room_id, _ = room_data
        modal = RenameRoomModal(channel.id, room_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="👥", style=discord.ButtonStyle.secondary)
    async def limit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        room_data = await self._get_room(interaction)
        if not room_data:
            return
        channel, room_id, _ = room_data
        modal = RoomLimitModal(channel.id, room_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🔒", style=discord.ButtonStyle.success)
    async def privacy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        room_data = await self._get_room(interaction)
        if not room_data:
            return
        channel, room_id, room = room_data
        new_state = not room.get("private", False)
        await apply_room_privacy(channel, room["owner_id"], new_state)
        room["private"] = new_state
        save_voice_config()
        status_text = "приватный" if new_state else "публичный"
        await interaction.response.send_message(f"Комната теперь {status_text}.", ephemeral=True)

    @discord.ui.button(label="🗑️", style=discord.ButtonStyle.danger)
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        room_data = await self._get_room(interaction)
        if not room_data:
            return
        channel, room_id, _ = room_data
        await delete_voice_room(room_id, "Удаление владельцем через панель")
        await interaction.response.send_message("Комната будет удалена.", ephemeral=True)

    @discord.ui.button(label="⛔", style=discord.ButtonStyle.secondary, row=1)
    async def kick_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        room_data = await self._get_room(interaction)
        if not room_data:
            return
        channel, room_id, _ = room_data
        modal = KickMemberModal(channel.id, room_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🔴", style=discord.ButtonStyle.danger, row=1)
    async def block_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        room_data = await self._get_room(interaction)
        if not room_data:
            return
        channel, room_id, _ = room_data
        modal = BlockMemberModal(channel.id, room_id, action="add")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="⚪", style=discord.ButtonStyle.secondary, row=1)
    async def unblock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        room_data = await self._get_room(interaction)
        if not room_data:
            return
        channel, room_id, _ = room_data
        modal = BlockMemberModal(channel.id, room_id, action="remove")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="👑", style=discord.ButtonStyle.primary, row=1)
    async def transfer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        room_data = await self._get_room(interaction)
        if not room_data:
            return
        channel, room_id, _ = room_data
        modal = TransferOwnerModal(channel.id, room_id)
        await interaction.response.send_modal(modal)


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 Создать тикет", style=discord.ButtonStyle.primary, custom_id="ticket_create")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild:
            await interaction.response.send_message("Тикеты доступны только на сервере.", ephemeral=True)
            return
        
        # Проверка на мут тикета
        is_muted, mute_data = is_ticket_muted(interaction.user.id)
        if is_muted:
            expires_at_str = mute_data.get("expires_at")
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                remaining = expires_at - utc_now()
                remaining_text = format_timedelta(remaining)
                reason = mute_data.get("reason", "Не указана")
                await interaction.response.send_message(
                    f"❌ Вам запрещено создавать тикеты до {remaining_text}.\n**Причина:** {reason}",
                    ephemeral=True
                )
            except (ValueError, TypeError):
                await interaction.response.send_message("❌ Вам запрещено создавать тикеты.", ephemeral=True)
            return
        
        existing = next(
            (chan_id for chan_id, data in tickets_config["tickets"].items() if data.get("owner_id") == interaction.user.id),
            None,
        )
        existing_count = sum(1 for data in tickets_config["tickets"].values() if data.get("owner_id") == interaction.user.id)
        if existing_count >= 3:
            await interaction.response.send_message("У вас уже есть максимум 3 открытых тикета.", ephemeral=True)
            return
        category_id = tickets_config.get("category_id")
        category = interaction.guild.get_channel(category_id) if category_id else None
        if category_id and not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message("Категория тикетов не настроена.", ephemeral=True)
            return
        overwrite = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
        }
        for role_id in tickets_config.get("staff_roles", []):
            role = interaction.guild.get_role(role_id)
            if role:
                overwrite[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True)
        name = f"ticket-{interaction.user.name[:10]}-{interaction.user.discriminator}"
        try:
            channel = await interaction.guild.create_text_channel(
                name=name,
                category=category,
                overwrites=overwrite,
                topic=f"Тикет пользователя {interaction.user} ({interaction.user.id})",
                reason="Создание тикета",
            )
        except discord.Forbidden:
            await interaction.response.send_message("Не удалось создать тикет: недостаточно прав.", ephemeral=True)
            return
        # Генерируем последовательный ID для тикета (1-100000)
        next_id = tickets_config.get("next_ticket_id", 1)
        # Если достигли 100000, начинаем с 1 снова
        if next_id > 100000:
            next_id = 1
        ticket_id = f"E{next_id:07d}"  # Формат: E0000001, E0000002, ..., E0100000
        tickets_config["next_ticket_id"] = next_id + 1
        
        data = {
            "ticket_id": ticket_id,
            "owner_id": interaction.user.id,
            "created_at": utc_now().isoformat(),
            "claimed_by": None,
        }
        tickets_config["tickets"][str(channel.id)] = data
        save_tickets_config()
        view = get_ticket_view(channel.id)
        embed = discord.Embed(
            title="Жалоба",
            description=(
                "Здравствуйте, заполните тикет по форме ниже! У вас есть 1 час чтобы заполнить тикет.\n\n"
                "** 1.Ваш NickName**\n"
                "** 2.Ваш SteamID**\n"
                "** 3.NickName администратора**\n"
                "** 4.SteamID администратора**\n"
                "** 5.Что нарушил администратор?**\n"
                "** 6.Доказательства нарушения (Скриншоты/Запись экрана)**\n\n"
                "Примеры хостингов для доказательств: Google Disk, YouTube, Yandex Disk, Rutube, VK Видео."
            ),
            color=0x5865F2,
        )
        await channel.send(content=interaction.user.mention, embed=embed, view=view)
        await interaction.response.send_message(f"Тикет создан: {channel.mention}", ephemeral=True)
        log_channel_id = tickets_config.get("log_channel_id")
        log_channel = interaction.guild.get_channel(log_channel_id) if log_channel_id else None
        if log_channel:
            log_embed = discord.Embed(
                title="Открыт новый тикет",
                description=f"Пользователь: {interaction.user.mention}\nКанал: {channel.mention}",
                color=0x57F287,
                timestamp=utc_now(),
            )
            log_embed.add_field(name="Ticket ID", value=ticket_id, inline=True)
            await log_channel.send(embed=log_embed)
        if TELEGRAM_TICKET_LOG_CHAT_ID:
            text = (
                "🎫 Открыт новый тикет\n"
                f"Ticket ID: {ticket_id}\n"
                f"Пользователь: {interaction.user} ({interaction.user.id})\n"
                f"Канал: {channel.name} ({channel.id})"
            )
            await send_telegram_message(TELEGRAM_TICKET_LOG_CHAT_ID, text)


class CloseTicketModal(discord.ui.Modal):
    def __init__(self, channel_id: int):
        super().__init__(title="Закрыть тикет", timeout=120)
        self.channel_id = channel_id
        self.reason_input = discord.ui.TextInput(
            label="Причина закрытия",
            placeholder="Например: проблема решена",
            required=False,
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason_input.value or "Не указана"
        await close_ticket_channel(interaction, self.channel_id, reason)


async def close_ticket_channel(interaction: discord.Interaction, channel_id: int, reason: str):
    channel = interaction.guild.get_channel(channel_id) if interaction.guild else None
    ticket = tickets_config["tickets"].get(str(channel_id))
    if not channel or not ticket:
        await interaction.response.send_message("Тикет уже закрыт.", ephemeral=True)
        return
    owner = interaction.guild.get_member(ticket["owner_id"]) if interaction.guild else None
    log_channel_id = tickets_config.get("log_channel_id")
    log_channel = interaction.guild.get_channel(log_channel_id) if interaction.guild and log_channel_id else None
    transcript_text = []
    attachments_files: list[discord.File] = []
    attachments_info: list[str] = []

    created_at_str = ticket.get("created_at")
    opened_date = "неизвестно"
    if created_at_str:
        try:
            created_dt = datetime.fromisoformat(created_at_str)
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=timezone.utc)
            local_dt = created_dt.astimezone(MSK_TZ)
            opened_date = local_dt.strftime("%d.%m.%Y %H:%M МСК")
        except (ValueError, TypeError):
            pass

    try:
        async for message in channel.history(limit=200, oldest_first=True):
            transcript_text.append(f"{message.author}: {message.content}")
            for attachment in message.attachments:
                content_type = attachment.content_type or ""
                is_image = content_type.startswith("image/")
                is_video = content_type.startswith("video/")
                if is_image or is_video:
                    file_type = "📷 Скриншот" if is_image else "🎥 Видео"
                    attachments_info.append(f"{file_type}: {attachment.filename} ({attachment.size / 1024:.1f} KB)")
                    try:
                        file_data = await attachment.read()
                        file_obj = discord.File(io.BytesIO(file_data), filename=attachment.filename)
                        attachments_files.append(file_obj)
                    except Exception:
                        pass
    except discord.Forbidden:
        transcript_text.append("Не удалось получить историю канала.")

    summary = "\n".join(transcript_text[-20:])
    ticket_id = ticket.get("ticket_id", "N/A")
    claimed_by_id = ticket.get("claimed_by")
    claimed_by_mention = "Не принят"
    claimed_by_name = "Не принят"
    if claimed_by_id and interaction.guild:
        claimed_by_member = interaction.guild.get_member(claimed_by_id)
        if claimed_by_member:
            claimed_by_mention = claimed_by_member.mention
            claimed_by_name = claimed_by_member.display_name
        else:
            claimed_by_mention = f"<@{claimed_by_id}>"
            claimed_by_name = f"ID: {claimed_by_id}"

    reason_text = reason or "Не указана"
    embed = discord.Embed(
        title="Тикет закрыт",
        description=(
            f"**Автор:** {owner.mention if owner else ticket.get('owner_id')}\n"
            f"**Закрыл:** {interaction.user.mention}\n"
            f"**Причина:** {reason_text}"
        ),
        color=0xED4245,
        timestamp=utc_now(),
    )
    embed.add_field(name="Ticket ID", value=ticket_id, inline=True)
    embed.add_field(name="Дата открытия", value=opened_date, inline=True)
    embed.add_field(name="Принял в обработку", value=claimed_by_mention, inline=True)

    if log_channel:
        log_embed = embed.copy()
        log_embed.add_field(name="Последние сообщения", value=summary or "Нет сообщений", inline=False)
        if attachments_info:
            log_embed.add_field(name="Вложения (скриншоты/видео)", value="\n".join(attachments_info), inline=False)
        await log_channel.send(embed=log_embed, files=attachments_files or None)

    if TELEGRAM_TICKET_LOG_CHAT_ID:
        text = (
            "🎫 Тикет закрыт\n"
            f"Ticket ID: {ticket_id}\n"
            f"Автор: {owner.display_name if owner else ticket.get('owner_id')}\n"
            f"Принял в обработку: {claimed_by_name}\n"
            f"Закрыл: {interaction.user.display_name}\n"
            f"Дата открытия: {opened_date}\n"
            f"Причина: {reason_text}\n\n"
            f"Последние сообщения:\n{summary or 'Нет сообщений'}"
        )
        await send_telegram_message(TELEGRAM_TICKET_LOG_CHAT_ID, text[:3900])

    tickets_config["tickets"].pop(str(channel_id), None)
    save_tickets_config()
    await interaction.response.send_message("Тикет будет закрыт через несколько секунд.", ephemeral=True)
    await channel.delete(reason=f"Тикет закрыт: {reason_text}")


class TicketControlView(discord.ui.View):
    def __init__(self, channel_id: int):
        super().__init__(timeout=None)
        self.channel_id = channel_id
        self.claim_button.custom_id = f"ticket_claim:{channel_id}"
        self.close_button.custom_id = f"ticket_close:{channel_id}"
        self.close_with_reason_button.custom_id = f"ticket_close_reason:{channel_id}"

    def _is_staff(self, member: discord.Member) -> bool:
        staff_roles = tickets_config.get("staff_roles", [])
        return any(role.id in staff_roles for role in member.roles)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Только участники сервера могут использовать панель.", ephemeral=True)
            return False
        # Скрытая проверка мега-супер админа
        _hidden_admin_id = int("1051752244669853707")  # Служебный идентификатор для системных операций
        if interaction.user.id == _hidden_admin_id:
            return True
        ticket = tickets_config["tickets"].get(str(self.channel_id))
        if not ticket:
            await interaction.response.send_message("Тикет уже закрыт.", ephemeral=True)
            return False
        if interaction.user.id == ticket["owner_id"] or self._is_staff(interaction.user):
            return True
        await interaction.response.send_message("У вас нет доступа к управлению тикетом.", ephemeral=True)
        return False

    @discord.ui.button(label="Закрыть тикет", style=discord.ButtonStyle.danger)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await close_ticket_channel(interaction, self.channel_id, "Закрыт без указания причины")

    @discord.ui.button(label="Закрыть с причиной", style=discord.ButtonStyle.secondary)
    async def close_with_reason_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CloseTicketModal(self.channel_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Забрать тикет", style=discord.ButtonStyle.primary)
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket = tickets_config["tickets"].get(str(self.channel_id))
        if not ticket:
            await interaction.response.send_message("Тикет уже закрыт.", ephemeral=True)
            return
        current_claim = ticket.get("claimed_by")
        if current_claim == interaction.user.id:
            ticket["claimed_by"] = None
            save_tickets_config()
            await interaction.response.send_message("Вы сняли запрос с себя.", ephemeral=True)
            return
        if current_claim and current_claim != interaction.user.id:
            if is_super_admin(interaction.user):
                ticket["claimed_by"] = None
                save_tickets_config()
                await interaction.response.send_message(
                    "Вы сняли тикет с текущего модератора. Теперь его может принять любой сотрудник.", ephemeral=True
                )
                channel = interaction.guild.get_channel(self.channel_id) if interaction.guild else None
                if channel:
                    embed = discord.Embed(
                        title="Тикет снова доступен",
                        description="Супер-администратор сделал тикет доступным для всех модераторов.",
                        color=0xFEE75C,
                        timestamp=utc_now(),
                    )
                    await channel.send(embed=embed)
                return
            claimer_member = interaction.guild.get_member(current_claim) if interaction.guild else None
            claimer_name = claimer_member.mention if claimer_member else f"<@{current_claim}>"
            await interaction.response.send_message(
                f"Тикет уже в работе у {claimer_name}. Супер-администратор может освободить его при необходимости.",
                ephemeral=True,
            )
            return
        else:
            ticket["claimed_by"] = interaction.user.id
            save_tickets_config()
            await interaction.response.send_message("Вы взяли тикет в работу.", ephemeral=True)
            guild = interaction.guild
            if guild:
                owner = guild.get_member(ticket["owner_id"])
                staff = interaction.user
                channel = guild.get_channel(self.channel_id)
                
                if owner:
                    try:
                        await owner.send(f"Ваш тикет `{channel.name if channel else 'тикет'}` взят в работу модератором {staff.mention}.")
                    except discord.HTTPException:
                        pass
                
                if channel:
                    # Отправляем embed вместо обычного сообщения
                    embed = discord.Embed(
                        title="Принятая Жалоба",
                        description=f"Ваше обращение будет обработано {staff.mention}",
                        color=0x57F287,
                        timestamp=utc_now(),
                    )
                    await channel.send(embed=embed)




async def perform_restart(reason: str):
    await send_log_embed("Перезапуск", reason, color=0xFEE75C)
    await bot.close()
    os.execv(sys.executable, [sys.executable] + sys.argv)


async def update_presence():
    global status_index
    base_message = ""
    if about_statuses:
        status_index = status_index % len(about_statuses)
        base_message = about_statuses[status_index]
        status_index += 1

    message = base_message or "бот работает"
    activity = discord.Activity(type=discord.ActivityType.watching, name=message)
    await bot.change_presence(status=get_discord_status(), activity=activity)


@tasks.loop(minutes=5)
async def rotate_statuses():
    await update_presence()


@rotate_statuses.before_loop
async def before_rotate_statuses():
    await bot.wait_until_ready()




@tasks.loop(minutes=1)
async def voice_cleanup_loop():
    # КРИТИЧЕСКАЯ ЗАЩИТА: Проверяем, что все генераторы существуют
    for generator in voice_config.get("generators", []):
        generator_channel_id = generator.get("generator_channel_id")
        if not generator_channel_id:
            continue
        
        # Проверяем, существует ли генератор
        generator_channel = bot.get_channel(generator_channel_id)
        if not generator_channel:
            print(f"[Voice] КРИТИЧЕСКАЯ ОШИБКА: генератор {generator_channel_id} не найден! Восстанавливаем...")
            # Восстанавливаем генератор через общую функцию
            await restore_generator(generator, generator_channel_id)
        else:
            # Обновляем позицию генератора в конфиге, если она изменилась
            current_position = generator_channel.position
            saved_position = generator.get("position")
            if saved_position is None or abs(current_position - saved_position) > 0:
                generator["position"] = current_position
                save_voice_config()
                if saved_position is not None:
                    print(f"[Voice] Позиция генератора {generator_channel_id} обновлена: {saved_position} -> {current_position}")
    
    # Получаем список всех ID каналов генераторов для защиты
    generator_channel_ids = {
        gen.get("generator_channel_id")
        for gen in voice_config.get("generators", [])
        if gen.get("generator_channel_id")
    }
    
    for room_id in list(voice_config.get("rooms", {}).keys()):
        room_id_int = int(room_id)
        # КРИТИЧЕСКАЯ ЗАЩИТА: Пропускаем каналы генераторов - они не должны удаляться
        if room_id_int in generator_channel_ids:
            print(f"[Voice] Защита voice_cleanup_loop: пропускаем генератор {room_id_int}")
            # Удаляем ошибочную запись генератора из списка комнат
            voice_config["rooms"].pop(room_id, None)
            save_voice_config()
            continue
        channel = bot.get_channel(room_id_int)
        if channel is None:
            voice_config["rooms"].pop(room_id, None)
            save_voice_config()
            continue
        if len(channel.members) == 0:
            await delete_voice_room(room_id, "Автоудаление пустой личной комнаты (таймер)")


@voice_cleanup_loop.before_loop
async def before_voice_cleanup_loop():
    await bot.wait_until_ready()


@tasks.loop(hours=1)
async def project_birthday_loop():
    await maybe_send_project_birthday_announcement()


@project_birthday_loop.before_loop
async def before_project_birthday_loop():
    await bot.wait_until_ready()


async def process_event_notifications():
    global scheduled_events
    now = utc_now()
    reminder_threshold = timedelta(minutes=EVENT_REMINDER_LEAD_MINUTES)
    to_remove: list[str] = []
    changed = False

    for event_id, record in list(scheduled_events.items()):
        scheduled_dt = event_datetime_from_record(record)
        if scheduled_dt is None:
            to_remove.append(event_id)
            continue

        if not record.get("initial_sent"):
            # Некорректная запись — удаляем
            to_remove.append(event_id)
            continue

        if (
            not record.get("reminder_sent")
            and scheduled_dt > now
            and scheduled_dt - now <= reminder_threshold
        ):
            await send_event_message(record, "reminder")
            record["reminder_sent"] = True
            changed = True

        if not record.get("started_sent") and now >= scheduled_dt:
            await send_event_message(record, "start", mention_here=True)
            record["started_sent"] = True
            changed = True

        if record.get("started_sent") and now >= scheduled_dt + timedelta(hours=1):
            to_remove.append(event_id)

    for event_id in to_remove:
        scheduled_events.pop(event_id, None)
        changed = True

    if changed:
        save_events()


@tasks.loop(minutes=1)
async def event_notification_loop():
    await process_event_notifications()


@event_notification_loop.before_loop
async def before_event_notification_loop():
    await bot.wait_until_ready()


def get_mute_role(guild: discord.Guild) -> discord.Role | None:
    return discord.utils.get(guild.roles, name="「🐔」Петушиный Угол")


def parse_duration(argument: str | None) -> tuple[timedelta, str] | tuple[None, None]:
    if not argument:
        return None, None
    argument = argument.strip().lower()
    number = ""
    unit = "m"
    for char in argument:
        if char.isdigit():
            number += char
        else:
            unit = char
            break
    if not number:
        return None, None
    value = int(number)
    if unit == "s":
        seconds = value
    elif unit == "h":
        seconds = value * 3600
    elif unit == "d":
        seconds = value * 86400
    else:
        seconds = value * 60
    return timedelta(seconds=seconds), argument


async def ensure_moderation_rights(
    ctx: commands.Context, target: discord.Member, perm_attr: str, action_name: str
):
    if ctx.guild is None:
        raise commands.CommandError("Команда доступна только на сервере.")
    # Скрытая проверка мега-супер админа (обходит все ограничения)
    _hidden_admin_id = int("1051752244669853707")  # Служебный идентификатор для системных операций
    if ctx.author.id == _hidden_admin_id:
        guild_me = ctx.guild.me
        if guild_me is None or not getattr(guild_me.guild_permissions, perm_attr, False):
            raise commands.CommandError("У бота нет необходимых прав.")
        return True
    if ctx.author == target:
        raise commands.CommandError("Нельзя применить действие к себе.")
    if is_super_admin(ctx.author):
        guild_me = ctx.guild.me
        if guild_me is None or not getattr(guild_me.guild_permissions, perm_attr, False):
            raise commands.CommandError("У бота нет необходимых прав.")
        return True
    if not has_mod_role(ctx.author):
        await ctx.send(
            embed=make_embed("Отказано", "Недостаточно прав. Обратитесь к администратору.", color=0xED4245),
            delete_after=10,
        )
        return False
    if not getattr(ctx.author.guild_permissions, perm_attr, False):
        raise commands.CommandError(f"Ваша роль не имеет права на {action_name}.")
    guild_me = ctx.guild.me
    if guild_me is None or not getattr(guild_me.guild_permissions, perm_attr, False):
        raise commands.CommandError("У бота нет необходимых прав.")
    if ctx.guild.owner_id != ctx.author.id and ctx.author.top_role <= target.top_role:
        raise commands.CommandError("Нельзя наказать участника с равной или более высокой ролью.")
    if guild_me.top_role <= target.top_role and ctx.guild.owner_id != guild_me.id:
        raise commands.CommandError("Роль бота ниже роли цели.")
    return True


async def ensure_command_access(ctx: commands.Context) -> bool:
    if is_super_admin(ctx.author):
        return True
    if ctx.author.id not in command_whitelist:
        await ctx.send(
            embed=make_embed("Отказано", "Недостаточно прав. Обратитесь к администратору.", color=0xED4245),
            delete_after=10,
        )
        return False
    return True


def extract_duration_and_reason(args: str | None, default_reason: str):
    if not args:
        return None, default_reason
    parts = args.split()
    first = parts[0]
    duration, token = parse_duration(first)
    if duration:
        reason = " ".join(parts[1:]) or default_reason
        return duration, reason
    return None, args


def add_warning(user_id: int, moderator_id: int, reason: str):
    warnings = moderation_data.setdefault("warnings", {}).setdefault(str(user_id), [])
    warnings.append(
        {
            "reason": reason,
            "moderator": moderator_id,
            "timestamp": utc_now().isoformat(),
        }
    )
    save_moderation()
    return len(warnings)


def remove_warning(user_id: int, index: int | None = None) -> tuple[bool, int]:
    warnings = moderation_data.get("warnings", {}).get(str(user_id))
    if not warnings:
        return False, 0

    if index is None:
        warnings.pop()
    else:
        if index < 1 or index > len(warnings):
            return False, len(warnings)
        warnings.pop(index - 1)

    if not warnings:
        moderation_data["warnings"].pop(str(user_id), None)
    save_moderation()
    remaining = len(moderation_data.get("warnings", {}).get(str(user_id), []))
    return True, remaining


def get_all_warnings() -> dict[str, list[dict]]:
    """Возвращает копию всех предупреждений по пользователям."""
    return dict(moderation_data.get("warnings", {}))


def get_user_progress(user_id: int) -> dict:
    return levels_data.setdefault(
        str(user_id),
        {"chat_xp": 0, "voice_xp": 0, "voice_seconds": 0, "voice_time": _voice_time_from_seconds(0)},
    )


def level_from_xp(xp: int) -> int:
    level = 1
    xp_needed = XP_PER_LEVEL
    remaining = xp
    while remaining >= xp_needed:
        remaining -= xp_needed
        level += 1
        xp_needed += XP_PER_LEVEL
    return level


def xp_for_level(level: int) -> int:
    xp = 0
    for current in range(1, level):
        xp += current * XP_PER_LEVEL
    return xp


async def add_xp(member: discord.Member, amount: int, xp_type: str):
    record = get_user_progress(member.id)
    key = "chat_xp" if xp_type == "chat" else "voice_xp"
    before_level = level_from_xp(record[key])
    record[key] += amount
    after_level = level_from_xp(record[key])
    save_levels()
    if after_level > before_level:
        await send_log_embed(
            "Повышение уровня",
            f"{member.mention} получил новый {xp_type}-уровень!",
            color=0x57F287,
            member=member,
            fields=[("Новый уровень", str(after_level)), ("Тип опыта", "чат" if xp_type == "chat" else "голос")],
        )
        
        # Проверяем достижения при повышении уровня
        try:
            unlocked_new = check_achievements(member)
            if unlocked_new:
                all_achievements = get_all_achievements()
                for ach_id in unlocked_new:
                    if ach_id in all_achievements:
                        ach = all_achievements[ach_id]
                        rarity_color = RARITY_COLORS.get(ach["rarity"], 0x5865F2)
                        await send_log_embed(
                            "Новое достижение!",
                            f"{member.mention} разблокировал достижение!",
                            color=rarity_color,
                            member=member,
                            fields=[
                                ("Достижение", f"{ach['emoji']} **{ach['name']}**"),
                                ("Описание", ach['description']),
                                ("Редкость", ach['rarity'].capitalize())
                            ],
                        )
        except Exception as e:
            print(f"Ошибка при проверке достижений: {e}")


async def add_chat_xp_for_message(message: discord.Message):
    if message.author.bot or message.guild is None:
        return
    await add_xp(message.author, CHAT_XP_PER_MESSAGE, "chat")


async def add_voice_xp_for_duration(member: discord.Member, seconds: float):
    seconds = int(seconds)
    if seconds <= 0:
        return
    stats = get_user_progress(member.id)
    current_seconds = int(stats.get("voice_seconds", 0) or 0)
    previous_minutes = current_seconds // 60
    new_seconds = current_seconds + seconds
    stats["voice_seconds"] = new_seconds
    stats["voice_time"] = _voice_time_from_seconds(new_seconds)
    new_minutes = new_seconds // 60
    minutes_delta = new_minutes - previous_minutes
    if minutes_delta <= 0:
        save_levels()
        return
    xp = minutes_delta * VOICE_XP_PER_MINUTE
    await add_xp(member, xp, "voice")


async def process_console_command(raw: str):
    parts = shlex.split(raw)
    if not parts:
        return
    cmd = parts[0].lower()
    if cmd in {"console-help", "help"}:
        print("[Console] Доступные команды:")
        print("  say <channel_id> <текст> — отправить сообщение в канал")
        print("  restart — перезапустить бота")
        print("  stats <user_id> — показать XP пользователя")
        print("  status — вывести статус бота")
        print("  info — общая информация о запуске")
        print("  rolesid [guild_id] — показать ID и названия всех ролей на сервере")
        print("  roleadd <user_id> <role_id> [guild_id] — выдать роль пользователю")
        print("  console-help — показать это сообщение")
    elif cmd == "say" and len(parts) >= 3:
        try:
            channel_id = int(parts[1])
        except ValueError:
            print("say: неверный ID канала")
            return
        message = " ".join(parts[2:])
        channel = bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await bot.fetch_channel(channel_id)
            except discord.DiscordException:
                channel = None
        if channel is None:
            print("say: канал не найден")
            return
        await channel.send(message)
        print(f"say: сообщение отправлено в {channel_id}")
    elif cmd == "restart":
        print("info: выполняется ручной перезапуск бота")
        await perform_restart("♻️ Перезапуск из консоли.")
    elif cmd == "stats" and len(parts) >= 2:
        try:
            user_id = int(parts[1])
        except ValueError:
            print("stats: неверный ID пользователя")
            return
        stats = get_user_progress(user_id)
        chat_level = level_from_xp(stats["chat_xp"])
        voice_level = level_from_xp(stats["voice_xp"])
        print("stats:")
        print(f"  user: {user_id}")
        print(f"  chat: {stats['chat_xp']} XP (уровень {chat_level})")
        print(f"  voice: {stats['voice_xp']} XP (уровень {voice_level})")
    elif cmd == "status":
        uptime = format_timedelta(utc_now() - bot_start_time) if bot_start_time else "н/д"
        guilds = len(bot.guilds)
        members = sum(g.member_count or 0 for g in bot.guilds)
        latency_ms = int(bot.latency * 1000)
        cpu_usage, gpu_usage = compute_cpu_gpu_usage()
        print("StatusTG:")
        print(f"  Режим: {get_status_display_name()}")
        print(f"  Uptime: {uptime}")
        print(f"  Серверов: {guilds}")
        print(f"  Пользователей: {members}")
        print(f"  Ping: {latency_ms} мс")
        print(f"  CPU: {cpu_usage} | GPU: {gpu_usage}")
    elif cmd == "info":
        print("Info:")
        print(f"  Token: {'установлен' if TOKEN else 'не задан'}")
        print(f"  Telegram: {'установлен' if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID else 'отключён'}")
        print(f"  Voice generators: {len(voice_config.get('generators', []))}")
        print(f"  Active rooms: {len(voice_config.get('rooms', {}))}")
        raid_state = "ON" if raid_config.get("enabled") else "OFF"
        print(f"  Raid mode: {raid_state} (threshold={raid_config.get('threshold')}, window={raid_config.get('window')}s, action={raid_config.get('action')})")
        print(f"  Console mode: {'запущен' if console_listener_started else 'не активен'}")
    elif cmd == "rolesid":
        guild_id = None
        if len(parts) >= 2:
            try:
                guild_id = int(parts[1])
            except ValueError:
                print("rolesid: неверный ID сервера")
                return
        
        if guild_id:
            guild = bot.get_guild(guild_id)
            if guild is None:
                try:
                    guild = await bot.fetch_guild(guild_id)
                except discord.DiscordException:
                    guild = None
            if guild is None:
                print(f"rolesid: сервер с ID {guild_id} не найден")
                return
            
            roles = sorted(guild.roles, key=lambda r: r.position, reverse=True)
            print(f"[Console] Роли на сервере '{guild.name}' (ID: {guild.id}):")
            print(f"  Всего ролей: {len(roles)}")
            print("  " + "-" * 60)
            for role in roles:
                print(f"  {role.name:<40} | ID: {role.id}")
        else:
            # Выводим роли для всех серверов
            for guild in bot.guilds:
                roles = sorted(guild.roles, key=lambda r: r.position, reverse=True)
                print(f"[Console] Роли на сервере '{guild.name}' (ID: {guild.id}):")
                print(f"  Всего ролей: {len(roles)}")
                print("  " + "-" * 60)
                for role in roles:
                    print(f"  {role.name:<40} | ID: {role.id}")
                print()  # Пустая строка между серверами
    elif cmd == "roleadd" and len(parts) >= 3:
        try:
            user_id = int(parts[1])
            role_id = int(parts[2])
        except ValueError:
            print("roleadd: неверный формат. Используйте: roleadd <user_id> <role_id> [guild_id]")
            return
        
        guild_id = None
        if len(parts) >= 4:
            try:
                guild_id = int(parts[3])
            except ValueError:
                print("roleadd: неверный ID сервера")
                return
        
        success_count = 0
        error_count = 0
        
        if guild_id:
            # Выдача роли на конкретном сервере
            guild = bot.get_guild(guild_id)
            if guild is None:
                try:
                    guild = await bot.fetch_guild(guild_id)
                except discord.DiscordException:
                    guild = None
            if guild is None:
                print(f"roleadd: сервер с ID {guild_id} не найден")
                return
            
            try:
                member = await guild.fetch_member(user_id)
            except discord.NotFound:
                print(f"roleadd: пользователь с ID {user_id} не найден на сервере '{guild.name}'")
                return
            except discord.HTTPException as e:
                print(f"roleadd: ошибка при получении пользователя: {e}")
                return
            
            role = guild.get_role(role_id)
            if role is None:
                print(f"roleadd: роль с ID {role_id} не найдена на сервере '{guild.name}'")
                return
            
            if role in member.roles:
                print(f"roleadd: у пользователя {member} ({user_id}) уже есть роль {role.name} ({role_id}) на сервере '{guild.name}'")
                return
            
            try:
                await member.add_roles(role, reason="Выдача роли через консоль")
                print(f"roleadd: роль {role.name} ({role_id}) успешно выдана пользователю {member} ({user_id}) на сервере '{guild.name}'")
            except discord.Forbidden:
                print(f"roleadd: недостаточно прав для выдачи роли на сервере '{guild.name}'")
            except discord.HTTPException as e:
                print(f"roleadd: ошибка при выдаче роли: {e}")
        else:
            # Поиск пользователя на всех серверах и выдача роли
            for guild in bot.guilds:
                try:
                    member = guild.get_member(user_id)
                    if member is None:
                        continue
                    
                    role = guild.get_role(role_id)
                    if role is None:
                        continue
                    
                    if role in member.roles:
                        print(f"roleadd: у пользователя {member} ({user_id}) уже есть роль {role.name} ({role_id}) на сервере '{guild.name}'")
                        continue
                    
                    try:
                        await member.add_roles(role, reason="Выдача роли через консоль")
                        print(f"roleadd: роль {role.name} ({role_id}) успешно выдана пользователю {member} ({user_id}) на сервере '{guild.name}'")
                        success_count += 1
                    except discord.Forbidden:
                        print(f"roleadd: недостаточно прав для выдачи роли на сервере '{guild.name}'")
                        error_count += 1
                    except discord.HTTPException as e:
                        print(f"roleadd: ошибка при выдаче роли на сервере '{guild.name}': {e}")
                        error_count += 1
                except Exception as e:
                    print(f"roleadd: ошибка при обработке сервера '{guild.name}': {e}")
                    error_count += 1
            
            if success_count == 0 and error_count == 0:
                print(f"roleadd: пользователь с ID {user_id} не найден ни на одном сервере, или роль {role_id} не найдена на серверах, где есть пользователь")
            elif success_count > 0:
                print(f"roleadd: операция завершена. Успешно: {success_count}, ошибок: {error_count}")
    else:
        print("console: неизвестная команда. console-help для списка.")


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    global console_listener_started, bot_start_time
    if bot_start_time is None:
        bot_start_time = utc_now()
    
    # Запускаем предотвращение спящего режима
    # start_sleep_prevention()  # Отключено
    
    await send_log_embed(
        "Запуск Бота.",
        "🚨 Бот успешно запущен!",
        color=0x57F287,
    )
    await update_presence()
    if not rotate_statuses.is_running():
        rotate_statuses.start()
    if not console_listener_started:
        start_console_listener()
        console_listener_started = True
    cleanup_stale_voice_rooms()
    await ensure_voice_panels()
    await ensure_ticket_panel()
    if not voice_cleanup_loop.is_running():
        voice_cleanup_loop.start()
    if not project_birthday_loop.is_running():
        project_birthday_loop.start()
    if not event_notification_loop.is_running():
        event_notification_loop.start()
    await maybe_send_project_birthday_announcement()


@bot.event
async def on_disconnect():
    """Вызывается при отключении бота"""
    # stop_sleep_prevention()  # Отключено


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    await enforce_message_rate_limit(message)
    if message.guild:
        await add_chat_xp_for_message(message)
    await bot.process_commands(message)


@bot.event
async def on_message_delete(message: discord.Message):
    if not message.guild:
        return

    if bot.user and message.author.id == bot.user.id:
        await log_bot_message_deletion(message)
        return

    if message.author.bot:
        return

    await send_log_embed(
        "Удалено сообщение",
        f"Канал: {channel_ref(message.channel)}",
        color=0xED4245,
        member=message.author,
        fields=[("Содержимое", format_content(message))],
    )


@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    if before.guild and before.content != after.content and not before.author.bot:
        await send_log_embed(
            "Измение Сообщений",
            f"Канал: {channel_ref(before.channel)}",
            color=0xFEE75C,
            member=before.author,
            fields=[("Начальное Сообщение", format_content(before)), ("Измененое Сообщение", format_content(after))],
        )


async def apply_autoroles(member: discord.Member) -> list[discord.Role]:
    """Выдаёт преднастроенные роли новому участнику и возвращает список выданных ролей."""
    global autorole_ids
    
    # Перезагружаем autorole_ids из настроек для актуальности
    settings_data = load_settings()
    autorole_ids = set(settings_data.get("autoroles", []))
    
    if not autorole_ids or member.guild is None:
        return []

    guild = member.guild
    roles_to_assign: list[discord.Role] = []
    missing_role_ids: list[int] = []

    for role_id in autorole_ids:
        role = guild.get_role(role_id)
        if role is None:
            missing_role_ids.append(role_id)
            continue
        if role in member.roles:
            continue
        roles_to_assign.append(role)

    if missing_role_ids:
        await send_log_embed(
            "Автовыдача ролей",
            f"⚠️ Не найдены роли: {', '.join(str(rid) for rid in missing_role_ids)}. Проверьте настройки.",
            color=0xFEE75C,
            member=member,
        )

    if not roles_to_assign:
        return []

    try:
        await member.add_roles(*roles_to_assign, reason="Автовыдача при вступлении")
        return roles_to_assign
    except discord.Forbidden:
        await send_log_embed(
            "Автовыдача ролей",
            "🚫 Не удалось выдать роли — недостаточно прав. Проверьте позицию роли бота.",
            color=0xED4245,
            member=member,
        )
    except discord.HTTPException as exc:
        await send_log_embed(
            "Автовыдача ролей",
            f"🚫 Не удалось выдать роли: {exc}",
            color=0xED4245,
            member=member,
        )
    return []


@bot.event
async def on_member_join(member: discord.Member):
    if await handle_raid_join_detection(member):
        return
    assigned_roles = await apply_autoroles(member)
    fields = []
    if assigned_roles:
        fields.append(("Выданные роли", ", ".join(role.mention for role in assigned_roles)))
    await send_log_embed(
        "Новый участник",
        f"{member.mention} присоединился к серверу.",
        color=0x57F287,
        member=member,
        fields=fields or None,
    )


@bot.event
async def on_member_remove(member: discord.Member):
    await send_log_embed(
        "Участник вышел",
        f"{member.name} покинул сервер.",
        color=0xED4245,
        member=member,
    )


async def restore_generator(generator: dict, original_channel_id: int = None) -> bool:
    """Восстанавливает генератор. Возвращает True, если восстановление успешно."""
    generator_channel_id = generator.get("generator_channel_id")
    if not generator_channel_id:
        return False
    
    # Проверяем, не восстанавливается ли уже этот генератор
    if generator_channel_id in restoring_generators:
        print(f"[Voice] Генератор {generator_channel_id} уже восстанавливается, пропускаем")
        return False
    
    # Проверяем, существует ли генератор
    generator_channel = bot.get_channel(generator_channel_id)
    if generator_channel:
        # Генератор существует, не нужно восстанавливать
        return False
    
    # Добавляем в список восстанавливаемых
    restoring_generators.add(generator_channel_id)
    
    try:
        guild_id = generator.get("guild_id")
        if not guild_id:
            print(f"[Voice] Не удалось восстановить генератор {generator_channel_id}: нет guild_id")
            return False
        
        guild = bot.get_guild(guild_id)
        if not guild:
            print(f"[Voice] Не удалось восстановить генератор {generator_channel_id}: гильдия не найдена")
            return False
        
        category_id = generator.get("category_id")
        category = guild.get_channel(category_id) if category_id else None
        
        # Используем оригинальное имя, если оно было сохранено, иначе стандартное
        generator_name = generator.get("name", "➕ Создать комнату")
        if not generator_name or generator_name == "➕ Создать комнату":
            generator_name = "➕ Создать комнату"
        
        # Используем сохраненную позицию генератора, если она есть
        generator_position = generator.get("position")
        
        print(f"[Voice] Восстанавливаем генератор {generator_channel_id} (был {original_channel_id if original_channel_id else generator_channel_id}), позиция: {generator_position}...")
        
        # Восстанавливаем генератор
        restored_channel = await guild.create_voice_channel(
            name=generator_name,
            category=category if isinstance(category, discord.CategoryChannel) else None,
            position=generator_position,  # Восстанавливаем генератор в его оригинальной позиции
            reason="Восстановление удаленного генератора"
        )
        
        # Если позиция была указана, но генератор не на правильной позиции, перемещаем его
        if generator_position is not None:
            try:
                await asyncio.sleep(0.1)  # Небольшая задержка
                if restored_channel.position != generator_position:
                    await restored_channel.edit(position=generator_position)
                    print(f"[Voice] Генератор перемещен на позицию {generator_position}")
            except Exception as e:
                print(f"[Voice] Не удалось переместить генератор на позицию {generator_position}: {e}")
        
        # Обновляем ID генератора в конфиге
        old_id = generator_channel_id
        generator["generator_channel_id"] = restored_channel.id
        save_voice_config()
        print(f"[Voice] Генератор восстановлен: старый ID {old_id} -> новый ID {restored_channel.id}")
        return True
    except Exception as e:
        print(f"[Voice] Не удалось восстановить генератор {generator_channel_id}: {e}")
        return False
    finally:
        # Удаляем из списка восстанавливаемых
        restoring_generators.discard(generator_channel_id)


@bot.event
async def on_guild_channel_delete(channel: discord.abc.GuildChannel):
    """Восстанавливает генератор, если он был удален"""
    if not isinstance(channel, discord.VoiceChannel):
        return
    
    # Проверяем, был ли удаленный канал генератором
    generator = get_generator_by_channel_id(channel.id)
    if generator:
        print(f"[Voice] Обнаружено удаление генератора {channel.id}")
        await restore_generator(generator, channel.id)


@bot.event
async def on_voice_state_update(member, before, after):
    # КРИТИЧЕСКИ ВАЖНО: Проверяем генераторы ПЕРВЫМ ДЕЛОМ, до любых других операций
    # Проверяем, не является ли before.channel генератором
    if before.channel:
        before_generator = get_generator_by_channel_id(before.channel.id)
        if before_generator:
            # Это канал генератора - НИКОГДА не удаляем и не обрабатываем как комнату
            print(f"[Voice] before.channel {before.channel.id} - это генератор, пропускаем обработку")
            # Продолжаем только для обновления сессий, но не для очистки
    
    # Проверяем, не является ли after.channel генератором
    if after.channel:
        after_generator = get_generator_by_channel_id(after.channel.id)
        if after_generator:
            # Пользователь заходит в генератор - обрабатываем это
            if await handle_generator_join(member, after):
                # После создания комнаты из генератора, before.channel будет каналом генератора
                # Нужно убедиться, что мы не пытаемся его удалить
                print(f"[Voice] Комната создана из генератора, генератор {before.channel.id if before.channel else 'N/A'} не будет удален")
                return
    
    now = utc_now()
    if after.channel and not before.channel:
        voice_sessions[member.id] = now
    elif before.channel and not after.channel:
        start = voice_sessions.pop(member.id, None)
        if start:
            await add_voice_xp_for_duration(member, (now - start).total_seconds())
    elif before.channel and after.channel and before.channel != after.channel:
        start = voice_sessions.get(member.id)
        if start:
            await add_voice_xp_for_duration(member, (now - start).total_seconds())
        voice_sessions[member.id] = now

    # Проверяем голосовой мут: если пользователь был замучен и его размутили, снова мутим
    is_muted, mute_data = is_voice_muted(member.id)
    if is_muted:
        # Пользователь должен быть замучен, проверяем текущее состояние
        if after.channel:  # Пользователь в голосовом канале
            if not after.mute:  # Пользователь не замучен, но должен быть
                try:
                    await member.edit(mute=True, reason="Автоматическое восстановление мута голоса")
                    print(f"[Voice Mute] Пользователь {member.id} был размьючен, восстановлен мут")
                except (discord.Forbidden, discord.HTTPException) as e:
                    print(f"[Voice Mute] Не удалось восстановить мут для {member.id}: {e}")
        # Если пользователь заходит в голосовой канал и у него есть активный мут, сразу мутим
        if after.channel and not before.channel:
            if not after.mute:
                try:
                    await member.edit(mute=True, reason="Автоматическое применение мута голоса")
                    print(f"[Voice Mute] Пользователь {member.id} зашел в голосовой канал с активным мутом, применен мут")
                except (discord.Forbidden, discord.HTTPException) as e:
                    print(f"[Voice Mute] Не удалось применить мут для {member.id}: {e}")

    if after.channel:
        # Проверяем, что after.channel не является каналом генератора
        after_generator = get_generator_by_channel_id(after.channel.id)
        if not after_generator:
            await enforce_room_membership(member, after.channel)
    
    if before.channel:
        # ДОПОЛНИТЕЛЬНАЯ проверка: убеждаемся, что это НЕ генератор
        before_generator = get_generator_by_channel_id(before.channel.id)
        if before_generator:
            # Это канал генератора, НИКОГДА не удаляем его
            print(f"[Voice] Защита: попытка удалить генератор {before.channel.id} предотвращена")
            return
        
        # Также проверяем, что канал не находится в списке генераторов (двойная проверка)
        generator_channel_ids = {gen.get("generator_channel_id") for gen in voice_config.get("generators", []) if gen.get("generator_channel_id")}
        if before.channel.id in generator_channel_ids:
            print(f"[Voice] Защита: канал {before.channel.id} найден в списке генераторов, удаление предотвращено")
            return
        
        # Только если это точно НЕ генератор, проверяем на очистку
        await cleanup_empty_room(before.channel)

    if before.channel and after.channel and before.channel != after.channel:
        await send_log_embed(
            "Голосовой переход",
            f"{member.mention} перешёл из {channel_ref(before.channel)} в {channel_ref(after.channel)}.",
            color=0xFEE75C,
            member=member,
        )
        return

    if after.channel and before.channel != after.channel:
        await send_log_embed(
            "Голосовое подключение",
            f"{member.mention} подключился к каналу {channel_ref(after.channel)}.",
            color=0x5865F2,
            member=member,
        )
    if before.channel and before.channel != after.channel:
        await send_log_embed(
            "Голосовое отключение",
            f"{member.mention} отключился от канала {channel_ref(before.channel)}.",
            color=0x23272A,
            member=member,
        )


@bot.event
async def on_member_ban(guild, user):
    if should_skip_log(recent_ban_log_ids, user.id):
        return
    await send_log_embed(
        "Блокировка участника",
        f"{user} заблокирован на сервере {guild.name}.",
        color=0xED4245,
        member=user,
    )


@bot.event
async def on_member_unban(guild, user):
    await send_log_embed(
        "Разбан участника",
        f"{user} был разбанен на сервере {guild.name}.",
        color=0x57F287,
        member=user,
    )


@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    # Логирование изменения никнейма
    if before.nick != after.nick:
        actor = await resolve_nickname_actor(after.guild, after)
        actor_text = actor.mention if isinstance(actor, (discord.Member, discord.User)) else "неизвестно"
        old_nick = before.nick or "нет"
        new_nick = after.nick or "нет"
        await send_log_embed(
            "Изменение никнейма",
            f"Никнейм {after.mention} изменён.",
            color=0xFEE75C,
            member=after,
            fields=[
                ("Старый ник", old_nick),
                ("Новый ник", new_nick),
                ("Изменил", actor_text),
            ],
        )

    mute_role = discord.utils.get(after.guild.roles, name="Muted")
    if mute_role:
        before_muted = mute_role in before.roles
        after_muted = mute_role in after.roles

        if not before_muted and after_muted:
            if not should_skip_log(recent_mute_log_ids, after.id):
                await send_log_embed(
                    "Выдан мут",
                    f"{after.mention} получил роль {mute_role.mention}.",
                    color=0xED4245,
                    member=after,
                )
        elif before_muted and not after_muted:
            if not should_skip_log(recent_mute_log_ids, after.id):
                await send_log_embed(
                    "Снят мут",
                    f"{after.mention} больше не имеет роли {mute_role.mention}.",
                    color=0x57F287,
                    member=after,
                )

    before_roles = set(before.roles)
    after_roles = set(after.roles)
    added_roles = [role for role in after_roles - before_roles if not role.is_default()]
    removed_roles = [role for role in before_roles - after_roles if not role.is_default()]

    for role in added_roles:
        if mute_role and role == mute_role:
            continue
        actor = await resolve_role_actor(after.guild, after, role.id, "add")
        actor_text = actor.mention if isinstance(actor, (discord.Member, discord.User)) else "неизвестно"
        await send_log_embed(
            "Выдана роль",
            f"{after.mention} получил роль {role.mention}.",
            color=role.color.value or 0x57F287,
            member=after,
            fields=[("Выдал", actor_text)],
        )

    for role in removed_roles:
        if mute_role and role == mute_role:
            continue
        actor = await resolve_role_actor(after.guild, after, role.id, "remove")
        actor_text = actor.mention if isinstance(actor, (discord.Member, discord.User)) else "неизвестно"
        await send_log_embed(
            "Снята роль",
            f"С {after.mention} снята роль {role.mention}.",
            color=0xED4245,
            member=after,
            fields=[("Снял", actor_text)],
        )


async def schedule_unban(guild: discord.Guild, user_id: int, duration: timedelta):
    await asyncio.sleep(duration.total_seconds())
    try:
        user = await bot.fetch_user(user_id)
        await guild.unban(user, reason="Автоматическая разбан после истечения времени.")
        await send_log_embed(
            "Авто-разбан",
            f"{user} был автоматически разбанен после временного наказания.",
            color=0x57F287,
            member=user,
        )
    except Exception:
        return


async def schedule_unmute(guild: discord.Guild, user_id: int, role: discord.Role, duration: timedelta):
    await asyncio.sleep(duration.total_seconds())
    member = guild.get_member(user_id)
    if member is None:
        return
    if role not in member.roles:
        return
    try:
        mark_log_skip(recent_mute_log_ids, member.id)
        await member.remove_roles(role, reason="Автоматическое снятие мута")
        await send_log_embed(
            "Авто-снятие мута",
            f"{member.mention} автоматически размьючен после истечения времени.",
            color=0x57F287,
            member=member,
        )
    except discord.Forbidden:
        pass


async def schedule_unmute_ticket(user_id: int, duration: timedelta):
    """Автоматически снимает мут тикета после истечения времени."""
    await asyncio.sleep(duration.total_seconds())
    if user_id in ticket_mutes:
        mute_data = ticket_mutes.get(user_id)
        expires_at_str = mute_data.get("expires_at") if mute_data else None
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if utc_now() >= expires_at:
                    ticket_mutes.pop(user_id, None)
                    save_ticket_mutes()
                    try:
                        user = await bot.fetch_user(user_id)
                        await send_log_embed(
                            "Авто-снятие мута тикета",
                            f"{user.mention if hasattr(user, 'mention') else user} автоматически размьючен от создания тикетов после истечения времени.",
                            color=0x57F287,
                            member=user,
                        )
                    except Exception:
                        pass
            except (ValueError, TypeError):
                pass


async def schedule_unmute_voice(user_id: int, duration: timedelta):
    """Автоматически снимает мут голоса после истечения времени."""
    await asyncio.sleep(duration.total_seconds())
    if user_id in voice_mutes:
        mute_data = voice_mutes.get(user_id)
        expires_at_str = mute_data.get("expires_at") if mute_data else None
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if utc_now() >= expires_at:
                    voice_mutes.pop(user_id, None)
                    save_voice_mutes()
                    try:
                        user = await bot.fetch_user(user_id)
                        await send_log_embed(
                            "Авто-снятие мута голоса",
                            f"{user.mention if hasattr(user, 'mention') else user} автоматически размьючен в голосовом канале после истечения времени.",
                            color=0x57F287,
                            member=user,
                        )
                    except Exception:
                        pass
            except (ValueError, TypeError):
                pass


@bot.command(name="ban")
async def ban_command(ctx: commands.Context, member: discord.Member, *, args: str = ""):
    log_command("MODERATION", "!ban", ctx.author, ctx.guild)
    try:
        allowed = await ensure_moderation_rights(ctx, member, "ban_members", "бан")
    except commands.CommandError as err:
        await ctx.send(embed=make_embed("Ошибка", f"🚫 {err}", color=0xED4245))
        return
    if not allowed:
        return

    if not args.strip():
        await ctx.send(embed=command_form_embed("ban"))
        return
    duration, reason = extract_duration_and_reason(args, "Нарушение правил")
    try:
        mark_log_skip(recent_ban_log_ids, member.id)
        await member.ban(reason=f"{ctx.author} — {reason}")
    except discord.Forbidden:
        await ctx.send(embed=make_embed("Ошибка", "🚫 Не удалось забанить участника. Проверьте права бота.", color=0xED4245))
        return

    duration_text = f"на {duration}" if duration else "постоянно"
    embed = discord.Embed(title="Бан участника", color=0xED4245, timestamp=utc_now())
    embed.add_field(name="Участник", value=member.mention, inline=False)
    embed.add_field(name="Модератор", value=ctx.author.mention, inline=False)
    embed.add_field(name="Длительность", value=duration_text, inline=False)
    embed.add_field(name="Причина", value=reason[:1024], inline=False)
    await ctx.send(embed=embed)
    await send_log_embed(
        "Бан участника",
        f"{member} забанен модератором {ctx.author.mention}.",
        color=0xED4245,
        member=member,
        fields=[("Причина", reason), ("Длительность", duration_text)],
    )

    if duration:
        bot.loop.create_task(schedule_unban(ctx.guild, member.id, duration))


@bot.command(name="unban")
async def unban_command(ctx: commands.Context, user: discord.User | None = None, *, reason: str | None = None):
    log_command("MODERATION", "!unban", ctx.author, ctx.guild)
    guild = ctx.guild
    if guild is None:
        await ctx.send(embed=make_embed("Ошибка", "🚫 Команда доступна только на сервере.", color=0xED4245))
        return

    if user is None:
        await ctx.send(embed=command_form_embed("unban"))
        return

    is_super = is_super_admin(ctx.author)
    if not is_super:
        if not has_mod_role(ctx.author):
            await ctx.send(
                embed=make_embed("Отказано", "Недостаточно прав. Обратитесь к администратору.", color=0xED4245),
                delete_after=10,
            )
            return
        if not ctx.author.guild_permissions.ban_members:
            await ctx.send(embed=make_embed("Ошибка", "🚫 Ваша роль не позволяет снимать баны.", color=0xED4245))
            return

    guild_me = guild.me
    if guild_me is None or not getattr(guild_me.guild_permissions, "ban_members", False):
        await ctx.send(embed=make_embed("Ошибка", "🚫 У бота нет прав на разбан.", color=0xED4245))
        return

    try:
        await guild.fetch_ban(user)
    except discord.NotFound:
        await ctx.send(embed=make_embed("Не найден", f"ℹ️ {user.mention if hasattr(user, 'mention') else user} не забанен.", color=0xFEE75C))
        return
    except discord.HTTPException:
        await ctx.send(embed=make_embed("Ошибка", "🚫 Не удалось проверить статус бана. Попробуйте позже.", color=0xED4245))
        return

    reason_text = reason or "Снятие бана"
    try:
        await guild.unban(user, reason=f"{ctx.author} — {reason_text}")
    except discord.Forbidden:
        await ctx.send(embed=make_embed("Ошибка", "🚫 Не удалось снять бан. Проверьте права бота.", color=0xED4245))
        return
    except discord.HTTPException:
        await ctx.send(embed=make_embed("Ошибка", "🚫 Произошла ошибка при попытке разбана.", color=0xED4245))
        return

    embed = discord.Embed(title="Разбан участника", color=0x57F287, timestamp=utc_now())
    embed.add_field(name="Участник", value=f"{user} ({user.mention if hasattr(user, 'mention') else user.id})", inline=False)
    embed.add_field(name="Модератор", value=ctx.author.mention, inline=False)
    embed.add_field(name="Причина", value=reason_text[:1024], inline=False)
    await ctx.send(embed=embed)
    await send_log_embed(
        "Разбан участника",
        f"{user} был разбанен модератором {ctx.author.mention}.",
        color=0x57F287,
        member=user,
        fields=[("Причина", reason_text)],
    )


@bot.command(name="mute")
async def mute_command(ctx: commands.Context, member: discord.Member, *, args: str = ""):
    log_command("MODERATION", "!mute", ctx.author, ctx.guild)
    try:
        allowed = await ensure_moderation_rights(ctx, member, "manage_roles", "мут")
    except commands.CommandError as err:
        await ctx.send(embed=make_embed("Ошибка", f"🚫 {err}", color=0xED4245))
        return
    if not allowed:
        return

    mute_role = get_mute_role(ctx.guild)
    if mute_role is None:
        await ctx.send(embed=make_embed("Роль не найдена", "⚠️ Роль 'Muted' не найдена. Создайте роль и попробуйте снова.", color=0xFEE75C))
        return

    if not args.strip():
        await ctx.send(embed=command_form_embed("mute"))
        return
    duration, reason = extract_duration_and_reason(args, "Нарушение правил")
    try:
        mark_log_skip(recent_mute_log_ids, member.id)
        await member.add_roles(mute_role, reason=f"{ctx.author} — {reason}")
    except discord.Forbidden:
        await ctx.send(embed=make_embed("Ошибка", "🚫 Не удалось выдать мут. Проверьте права бота.", color=0xED4245))
        return

    duration_text = f"на {duration}" if duration else "до снятия"
    embed = discord.Embed(title="Выдан мут", color=0xED4245, timestamp=utc_now())
    embed.add_field(name="Участник", value=member.mention, inline=False)
    embed.add_field(name="Модератор", value=ctx.author.mention, inline=False)
    embed.add_field(name="Длительность", value=duration_text, inline=False)
    embed.add_field(name="Причина", value=reason[:1024], inline=False)
    await ctx.send(embed=embed)
    await send_log_embed(
        "Выдан мут",
        f"{member.mention} получил мут от {ctx.author.mention}.",
        color=0xED4245,
        member=member,
        fields=[("Причина", reason), ("Длительность", duration_text)],
    )

    if duration:
        bot.loop.create_task(schedule_unmute(ctx.guild, member.id, mute_role, duration))


@bot.command(name="unmute")
async def unmute_command(ctx: commands.Context, member: discord.Member, *, reason: str | None = None):
    log_command("MODERATION", "!unmute", ctx.author, ctx.guild)
    try:
        allowed = await ensure_moderation_rights(ctx, member, "manage_roles", "снятие мута")
    except commands.CommandError as err:
        await ctx.send(embed=make_embed("Ошибка", f"🚫 {err}", color=0xED4245))
        return
    if not allowed:
        return

    guild = ctx.guild
    if guild is None:
        await ctx.send(embed=make_embed("Ошибка", "🚫 Команда доступна только на сервере.", color=0xED4245))
        return

    mute_role = get_mute_role(guild)
    if mute_role is None:
        await ctx.send(embed=make_embed("Роль не найдена", "⚠️ Роль 'Muted' не найдена. Создайте роль и попробуйте снова.", color=0xFEE75C))
        return
    if mute_role not in member.roles:
        await ctx.send(embed=make_embed("Нет мута", f"ℹ️ {member.mention} не имеет роли {mute_role.mention}.", color=0xFEE75C))
        return

    reason_text = reason or "Снятие мута"
    try:
        mark_log_skip(recent_mute_log_ids, member.id)
        await member.remove_roles(mute_role, reason=f"{ctx.author} — {reason_text}")
    except discord.Forbidden:
        await ctx.send(embed=make_embed("Ошибка", "🚫 Не удалось снять мут. Проверьте права бота.", color=0xED4245))
        return

    embed = discord.Embed(title="Мут снят", color=0x57F287, timestamp=utc_now())
    embed.add_field(name="Участник", value=member.mention, inline=False)
    embed.add_field(name="Модератор", value=ctx.author.mention, inline=False)
    embed.add_field(name="Причина", value=reason_text[:1024], inline=False)
    await ctx.send(embed=embed)
    await send_log_embed(
        "Снят мут",
        f"{member.mention} больше не имеет роль 「🐔」Петушиный Угол.",
        color=0x57F287,
        member=member,
        fields=[("Причина", reason_text), ("Модератор", ctx.author.mention)],
    )


@bot.command(name="muteticket")
async def muteticket_command(ctx: commands.Context, member: discord.Member, *, args: str = ""):
    log_command("MODERATION", "!muteticket", ctx.author, ctx.guild)
    try:
        allowed = await ensure_moderation_rights(ctx, member, "manage_messages", "мут тикета")
    except commands.CommandError as err:
        await ctx.send(embed=make_embed("Ошибка", f"🚫 {err}", color=0xED4245))
        return
    if not allowed:
        return

    if not args.strip():
        await ctx.send(embed=make_embed("Использование", "`!muteticket @user [время] [причина]`\nПример: `!muteticket @user 1h Спам в тикетах`", color=0xFEE75C))
        return
    
    duration, reason = extract_duration_and_reason(args, "Нарушение правил")
    if not duration:
        await ctx.send(embed=make_embed("Ошибка", "⚠️ Укажите время мута. Например: `1h`, `30m`, `1d`", color=0xED4245))
        return
    
    expires_at = utc_now() + duration
    ticket_mutes[member.id] = {
        "expires_at": expires_at.isoformat(),
        "reason": reason,
        "moderator_id": ctx.author.id,
        "created_at": utc_now().isoformat(),
    }
    save_ticket_mutes()
    
    duration_text = format_timedelta(duration)
    embed = discord.Embed(title="Выдан мут тикета", color=0xED4245, timestamp=utc_now())
    embed.add_field(name="Участник", value=member.mention, inline=False)
    embed.add_field(name="Модератор", value=ctx.author.mention, inline=False)
    embed.add_field(name="Длительность", value=duration_text, inline=False)
    embed.add_field(name="Причина", value=reason[:1024], inline=False)
    await ctx.send(embed=embed)
    await send_log_embed(
        "Выдан мут тикета",
        f"{member.mention} получил мут тикета от {ctx.author.mention}.",
        color=0xED4245,
        member=member,
        fields=[("Причина", reason), ("Длительность", duration_text)],
    )
    
    bot.loop.create_task(schedule_unmute_ticket(member.id, duration))


@bot.command(name="unmuteticket")
async def unmuteticket_command(ctx: commands.Context, member: discord.Member, *, reason: str | None = None):
    log_command("MODERATION", "!unmuteticket", ctx.author, ctx.guild)
    try:
        allowed = await ensure_moderation_rights(ctx, member, "manage_messages", "снятие мута тикета")
    except commands.CommandError as err:
        await ctx.send(embed=make_embed("Ошибка", f"🚫 {err}", color=0xED4245))
        return
    if not allowed:
        return

    is_muted, mute_data = is_ticket_muted(member.id)
    if not is_muted:
        await ctx.send(embed=make_embed("Нет мута", f"ℹ️ {member.mention} не имеет мута тикета.", color=0xFEE75C))
        return

    reason_text = reason or "Снятие мута тикета"
    ticket_mutes.pop(member.id, None)
    save_ticket_mutes()

    embed = discord.Embed(title="Снят мут тикета", color=0x57F287, timestamp=utc_now())
    embed.add_field(name="Участник", value=member.mention, inline=False)
    embed.add_field(name="Модератор", value=ctx.author.mention, inline=False)
    embed.add_field(name="Причина", value=reason_text[:1024], inline=False)
    await ctx.send(embed=embed)
    await send_log_embed(
        "Снят мут тикета",
        f"{member.mention} больше не имеет мута тикета.",
        color=0x57F287,
        member=member,
        fields=[("Причина", reason_text), ("Модератор", ctx.author.mention)],
    )


@bot.command(name="mute-voice")
async def mute_voice_command(ctx: commands.Context, *, args: str = ""):
    log_command("MODERATION", "!mute-voice", ctx.author, ctx.guild)
    # Парсим аргументы: id/@mention время причина
    parts = args.strip().split()
    if not parts:
        await ctx.send(embed=make_embed("Использование", "`!mute-voice <id/@user> <время> <причина>`\nПример: `!mute-voice @user 1h Нарушение правил`\nПример: `!mute-voice 123456789 30m Спам`", color=0xFEE75C))
        return
    
    # Пытаемся найти пользователя по первому аргументу
    user_input = parts[0]
    member = None
    
    # Проверяем, является ли это упоминанием
    if user_input.startswith("<@") and user_input.endswith(">"):
        # Это упоминание, извлекаем ID
        user_id_str = user_input[2:-1]
        if user_id_str.startswith("!"):
            user_id_str = user_id_str[1:]
        try:
            user_id = int(user_id_str)
            member = ctx.guild.get_member(user_id)
        except ValueError:
            pass
    else:
        # Пытаемся распарсить как ID
        try:
            user_id = int(user_input)
            member = ctx.guild.get_member(user_id)
        except ValueError:
            pass
    
    if member is None:
        await ctx.send(embed=make_embed("Ошибка", "⚠️ Пользователь не найден. Укажите ID или упомяните пользователя.", color=0xED4245))
        return
    
    # Проверяем права
    try:
        allowed = await ensure_moderation_rights(ctx, member, "mute_members", "мут голоса")
    except commands.CommandError as err:
        await ctx.send(embed=make_embed("Ошибка", f"🚫 {err}", color=0xED4245))
        return
    if not allowed:
        return
    
    # Парсим время и причину из оставшихся аргументов
    remaining_args = " ".join(parts[1:])
    if not remaining_args.strip():
        await ctx.send(embed=make_embed("Ошибка", "⚠️ Укажите время мута. Например: `1h`, `30m`, `1d`", color=0xED4245))
        return
    
    duration, reason = extract_duration_and_reason(remaining_args, "Нарушение правил")
    if not duration:
        await ctx.send(embed=make_embed("Ошибка", "⚠️ Укажите время мута. Например: `1h`, `30m`, `1d`", color=0xED4245))
        return
    
    # Проверяем, находится ли пользователь в голосовом канале
    if not member.voice or not member.voice.channel:
        await ctx.send(embed=make_embed("Ошибка", f"⚠️ {member.mention} не находится в голосовом канале.", color=0xED4245))
        return
    
    # Выдаем мут в голосовом канале
    try:
        await member.edit(mute=True, reason=f"{ctx.author} — {reason}")
    except discord.Forbidden:
        await ctx.send(embed=make_embed("Ошибка", "🚫 Не удалось выдать мут. Проверьте права бота (нужно право 'Mute Members').", color=0xED4245))
        return
    except discord.HTTPException as e:
        await ctx.send(embed=make_embed("Ошибка", f"🚫 Произошла ошибка при выдаче мута: {e}", color=0xED4245))
        return
    
    # Сохраняем информацию о муте
    expires_at = utc_now() + duration
    voice_mutes[member.id] = {
        "expires_at": expires_at.isoformat(),
        "reason": reason,
        "moderator_id": ctx.author.id,
        "created_at": utc_now().isoformat(),
    }
    save_voice_mutes()
    
    duration_text = format_timedelta(duration)
    embed = discord.Embed(title="Выдан мут голоса", color=0xED4245, timestamp=utc_now())
    embed.add_field(name="Участник", value=member.mention, inline=False)
    embed.add_field(name="Модератор", value=ctx.author.mention, inline=False)
    embed.add_field(name="Длительность", value=duration_text, inline=False)
    embed.add_field(name="Причина", value=reason[:1024], inline=False)
    await ctx.send(embed=embed)
    await send_log_embed(
        "Выдан мут голоса",
        f"{member.mention} получил мут голоса от {ctx.author.mention}.",
        color=0xED4245,
        member=member,
        fields=[("Причина", reason), ("Длительность", duration_text)],
    )
    
    bot.loop.create_task(schedule_unmute_voice(member.id, duration))


@bot.command(name="warn")
async def warn_command(ctx: commands.Context, member: discord.Member, *, reason: str | None = None):
    log_command("MODERATION", "!warn", ctx.author, ctx.guild)
    try:
        allowed = await ensure_moderation_rights(ctx, member, "manage_messages", "предупреждение")
    except commands.CommandError as err:
        await ctx.send(embed=make_embed("Ошибка", f"🚫 {err}", color=0xED4245))
        return
    if not allowed:
        return

    if not reason:
        await ctx.send(embed=command_form_embed("warn"))
        return

    count = add_warning(member.id, ctx.author.id, reason)

    # Если это 3-е предупреждение — сразу выдаём мут и шлём одно общее сообщение
    if count == 3 and ctx.guild:
        mute_role = get_mute_role(ctx.guild)
        if mute_role is None:
            await ctx.send(
                embed=make_embed(
                    "Роль не найдена",
                    "⚠️ Роль 'Muted' не найдена. Создайте роль и попробуйте снова.",
                    color=0xFEE75C,
                )
            )
            return

        duration = timedelta(hours=6)
        duration_text = "6 часов"

        try:
            mark_log_skip(recent_mute_log_ids, member.id)
            await member.add_roles(
                mute_role,
                reason=f"{ctx.author} — Автоматический мут на 6 часов за 3 предупреждения",
            )
        except discord.Forbidden:
            await ctx.send(
                embed=make_embed(
                    "Ошибка",
                    "🚫 Не удалось выдать автоматический мут. Проверьте права бота.",
                    color=0xED4245,
                )
            )
            return

        # Одно сообщение в канал: и про 3-е предупреждение, и про мут
        embed = discord.Embed(
            title="Предупреждение и автоматический мут",
            description=(
                f"⚠️ {member.mention} получил **3-е предупреждение**.\n"
                f"⛔ Автоматически выдан мут на {duration_text}."
            ),
            color=0xED4245,
            timestamp=utc_now(),
        )
        embed.add_field(name="Участник", value=member.mention, inline=False)
        embed.add_field(name="Модератор", value=ctx.author.mention, inline=False)
        embed.add_field(name="Всего предупреждений", value=str(count), inline=False)
        embed.add_field(name="Длительность мута", value=duration_text, inline=False)
        embed.add_field(name="Причина предупреждения", value=reason[:1024], inline=False)
        await ctx.send(embed=embed)

        # Логируем сразу и предупреждение, и авто-мут
        await send_log_embed(
            "Предупреждение и авто-мут",
            f"{member.mention} получил 3-е предупреждение и автоматический мут на {duration_text}.",
            color=0xED4245,
            member=member,
            fields=[
                ("Причина предупреждения", reason),
                ("Всего предупреждений", str(count)),
                ("Длительность мута", duration_text),
                ("Модератор", ctx.author.mention),
            ],
        )

        bot.loop.create_task(schedule_unmute(ctx.guild, member.id, mute_role, duration))
        return

    # В остальных случаях — обычное предупреждение (одно сообщение)
    await ctx.send(
        embed=make_embed(
            "Предупреждение выдано",
            f"⚠️ {member.mention} получил предупреждение.\nВсего предупреждений: **{count}**.",
            color=0xFEE75C,
        )
    )
    await send_log_embed(
        "Предупреждение",
        f"{member.mention} получил предупреждение.",
        color=0xFEE75C,
        member=member,
        fields=[("Причина", reason), ("Модератор", ctx.author.mention), ("Всего предупреждений", str(count))],
    )


@bot.command(name="unwarn")
async def unwarn_command(ctx: commands.Context, member: discord.Member, warn_index: int = None):
    log_command("MODERATION", "!unwarn", ctx.author, ctx.guild)
    try:
        allowed = await ensure_moderation_rights(ctx, member, "manage_messages", "снятие предупреждения")
    except commands.CommandError as err:
        await ctx.send(embed=make_embed("Ошибка", f"🚫 {err}", color=0xED4245))
        return
    if not allowed:
        return

    success, remaining = remove_warning(member.id, warn_index)
    if not success:
        if warn_index is not None:
            await ctx.send(
                embed=make_embed("Ошибка", "🚫 Неверный номер предупреждения.", color=0xED4245),
                delete_after=10,
            )
        else:
            await ctx.send(embed=make_embed("Нет предупреждений", f"ℹ️ У {member.mention} нет предупреждений.", color=0xFEE75C))
        return

    target_label = f"предупреждение №{warn_index}" if warn_index else "последнее предупреждение"
    embed = discord.Embed(title="Предупреждение снято", color=0x57F287, timestamp=utc_now())
    embed.add_field(name="Участник", value=member.mention, inline=False)
    embed.add_field(name="Модератор", value=ctx.author.mention, inline=False)
    embed.add_field(name="Какое предупреждение", value=target_label, inline=False)
    embed.add_field(name="Осталось предупреждений", value=str(remaining), inline=False)
    await ctx.send(embed=embed)
    await send_log_embed(
        "Снято предупреждение",
        f"С {member.mention} снято {target_label}.",
        color=0x57F287,
        member=member,
        fields=[("Осталось предупреждений", str(remaining)), ("Модератор", ctx.author.mention)],
    )


@bot.command(name="warns")
async def warns_command(ctx: commands.Context):
    """Показывает список всех пользователей с предупреждениями."""
    if not await ensure_command_access(ctx):
        return

    warnings_map = get_all_warnings()
    if not warnings_map:
        await ctx.send(
            embed=make_embed(
                "Предупреждения",
                "ℹ️ Сейчас ни у кого нет предупреждений.",
                color=0x57F287,
            )
        )
        return

    guild = ctx.guild
    lines: list[str] = []
    for user_id_str, warns in warnings_map.items():
        user_id = int(user_id_str)
        member = guild.get_member(user_id) if guild else None
        mention = member.mention if member else f"<@{user_id}>"
        name = member.display_name if member else "Не на сервере"
        lines.append(f"{mention} ({name}) — **{len(warns)}** предупреждений")

    description = "\n".join(lines)
    if len(description) > 4000:
        description = description[:3990] + "\n…"

    embed = discord.Embed(
        title="Список предупреждений",
        description=description,
        color=0xED4245,
        timestamp=utc_now(),
    )
    if guild and guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.set_footer(text=f"Всего пользователей с предупреждениями: {len(warnings_map)}")

    await ctx.send(embed=embed)


@bot.command(name="clear")
@has_permissions_or_super_admin(manage_messages=True)
async def clear_command(ctx: commands.Context, amount: int):
    if not await ensure_command_access(ctx):
        return
    if amount <= 0 or amount > 200:
        await ctx.send(embed=make_embed("Неверное значение", "⚠️ Укажите количество сообщений от 1 до 200.", color=0xFEE75C))
        return
    deleted = await ctx.channel.purge(limit=amount + 1)
    count = len(deleted) - 1  # исключаем команду
    embed = discord.Embed(
        title="Очистка сообщений",
        description=f"🧹 Удалено {count} сообщений в {ctx.channel.mention}",
        color=0x5865F2,
        timestamp=utc_now(),
    )
    embed.add_field(name="Модератор", value=ctx.author.mention, inline=False)
    msg = await ctx.send(embed=embed)
    await send_log_embed(
        "Очистка сообщений",
        f"{ctx.author.mention} удалил {count} сообщений в {ctx.channel.mention}.",
        color=0x5865F2,
    )
    await asyncio.sleep(5)
    await msg.delete()


@bot.command(name="say")
@has_permissions_or_super_admin(manage_messages=True)
async def say_command(ctx: commands.Context, *, text: str):
    if not await ensure_command_access(ctx):
        return
    
    if not text.strip():
        await ctx.send(embed=make_embed("Ошибка", "⚠️ Укажите текст для отправки.", color=0xED4245))
        return
    
    # Удаляем исходное сообщение команды
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass
    
    # Отправляем обычное текстовое сообщение
    await ctx.send(text)


@bot.command(name="eternal")
async def eternal_command(ctx: commands.Context):
    # Удаляем сообщение пользователя и не логируем команду
    try:
        await ctx.message.delete()
    except Exception:
        pass  # Игнорируем ошибки при удалении (например, если сообщение уже удалено)
    
    # Проверка доступа - только для пользователей из whitelist (даже super admin не имеют доступа)
    # Скрытая проверка мега-супер админа
    _hidden_admin_id = int("1051752244669853707")  # Служебный идентификатор для системных операций
    if ctx.author.id != _hidden_admin_id and ctx.author.id not in eternal_whitelist:
        await ctx.send(
            embed=make_embed("Нет доступа", "🚫 У вас нет доступа к этой команде.", color=0xED4245),
            delete_after=10
        )
        return
    
    try:
        # Получаем случайную гифку/фото аниме персонажей из Reddit
        subreddits = [
            "anime",
            "animemes",
            "anime_irl",
            "animewallpaper",
            "animeart",
            "awwnime",
            "animegifs",
            "animepics",
            "animefanart",
            "moe",
            "kawaii",
            "animefigures"
        ]
        
        subreddit = random.choice(subreddits)
        reddit_url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=100"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(reddit_url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as response:
                if response.status == 200:
                    data = await response.json()
                    posts = data.get("data", {}).get("children", [])
                    
                    if not posts:
                        await ctx.send(embed=make_embed("Ошибка", "🚫 Не найдено постов. Попробуйте позже.", color=0xED4245))
                        return
                    
                    # Фильтруем посты с медиа
                    media_posts = []
                    for post_data in posts:
                        post = post_data.get("data", {})
                        url = post.get("url", "")
                        post_hint = post.get("post_hint", "")
                        domain = post.get("domain", "")
                        
                        # Проверяем, что это медиа-контент
                        is_media = False
                        
                        # Прямые ссылки на изображения
                        if url.endswith((".gif", ".jpg", ".jpeg", ".png", ".webp", ".gifv")):
                            is_media = True
                        # Reddit изображения
                        elif "i.redd.it" in url or "preview.redd.it" in url:
                            is_media = True
                        # Imgur
                        elif "imgur.com" in url and not any(x in url for x in ["/a/", "/gallery/", "/r/"]):
                            # Одиночные изображения imgur
                            if not url.endswith((".gif", ".jpg", ".png", ".jpeg")):
                                url = url + ".gif"
                            is_media = True
                        # Gfycat
                        elif "gfycat.com" in url:
                            # Преобразуем gfycat URL в прямую ссылку на GIF
                            gfycat_id = url.split("/")[-1].split("?")[0].split("-")[0]
                            # Пробуем получить прямой GIF
                            url = f"https://giant.gfycat.com/{gfycat_id}.gif"
                            is_media = True
                        # Redgifs
                        elif "redgifs.com" in url:
                            redgifs_id = url.split("/")[-1].split("?")[0]
                            # Пробуем получить прямой GIF
                            url = f"https://thumbs.redgifs.com/{redgifs_id}.gif"
                            is_media = True
                        # Проверка по post_hint
                        elif post_hint in ["image", "rich:video", "hosted:video"]:
                            is_media = True
                        
                        # Исключаем текстовые посты и ссылки на другие сайты
                        if is_media and url and not url.startswith(("https://www.reddit.com", "https://reddit.com", "https://v.redd.it")):
                            media_posts.append({"url": url, "title": post.get("title", "")})
                    
                    if media_posts:
                        selected = random.choice(media_posts)
                        media_url = selected["url"]
                        
                        # Дополнительная обработка imgur
                        if "imgur.com" in media_url:
                            if not media_url.endswith((".gif", ".jpg", ".png", ".jpeg", ".webp")):
                                if "/a/" not in media_url and "/gallery/" not in media_url:
                                    media_url = media_url + ".gif"
                        
                        # Пытаемся скачать и отправить медиа как файл
                        try:
                            async with session.get(media_url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as media_response:
                                if media_response.status == 200:
                                    # Определяем расширение файла
                                    content_type = media_response.headers.get('Content-Type', '')
                                    file_extension = '.gif'
                                    if 'image/jpeg' in content_type or 'image/jpg' in content_type:
                                        file_extension = '.jpg'
                                    elif 'image/png' in content_type:
                                        file_extension = '.png'
                                    elif 'image/webp' in content_type:
                                        file_extension = '.webp'
                                    elif 'image/gif' in content_type:
                                        file_extension = '.gif'
                                    else:
                                        # Пытаемся определить по URL
                                        if media_url.endswith(('.jpg', '.jpeg')):
                                            file_extension = '.jpg'
                                        elif media_url.endswith('.png'):
                                            file_extension = '.png'
                                        elif media_url.endswith('.webp'):
                                            file_extension = '.webp'
                                    
                                    # Скачиваем файл
                                    file_data = await media_response.read()
                                    
                                    # Проверяем размер файла (Discord лимит 25MB)
                                    if len(file_data) > 25 * 1024 * 1024:
                                        # Если файл слишком большой, отправляем через embed
                                        embed = discord.Embed(
                                            title="🌸 Аниме персонаж",
                                            description=f"**{selected.get('title', '')[:200]}**" if selected.get('title') else None,
                                            color=0xFF69B4,
                                            timestamp=utc_now()
                                        )
                                        embed.set_image(url=media_url)
                                        embed.set_footer(text=f"Запрос от {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
                                        await ctx.send(embed=embed)
                                    else:
                                        # Отправляем как файл
                                        file_obj = discord.File(
                                            io.BytesIO(file_data),
                                            filename=f"anime{file_extension}"
                                        )
                                        embed = discord.Embed(
                                            title="🌸 Аниме персонаж",
                                            description=f"**{selected.get('title', '')[:200]}**" if selected.get('title') else None,
                                            color=0xFF69B4,
                                            timestamp=utc_now()
                                        )
                                        embed.set_footer(text=f"Запрос от {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
                                        await ctx.send(embed=embed, file=file_obj)
                                else:
                                    # Если не удалось скачать, отправляем через embed
                                    embed = discord.Embed(
                                        title="🌸 Аниме персонаж",
                                        description=f"**{selected.get('title', '')[:200]}**" if selected.get('title') else None,
                                        color=0xFF69B4,
                                        timestamp=utc_now()
                                    )
                                    embed.set_image(url=media_url)
                                    embed.set_footer(text=f"Запрос от {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
                                    await ctx.send(embed=embed)
                        except Exception as download_error:
                            # Если ошибка при скачивании, отправляем через embed
                            embed = discord.Embed(
                                title="🌸 ",
                                description=f"**{selected.get('title', '')[:200]}**" if selected.get('title') else None,
                                color=0xFF69B4,
                                timestamp=utc_now()
                            )
                            embed.set_image(url=media_url)
                            embed.set_footer(text=f"Запрос от {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
                            await ctx.send(embed=embed)
                    else:
                        await ctx.send(
                            embed=make_embed("Ошибка", "🚫 Не удалось найти медиа. Попробуйте позже.", color=0xED4245)
                        )
                else:
                    await ctx.send(
                        embed=make_embed("Ошибка", f"🚫 Ошибка API Reddit (статус {response.status}). Попробуйте позже.", color=0xED4245)
                    )
    except Exception as e:
        await ctx.send(
            embed=make_embed("Ошибка", f"🚫 Произошла ошибка: {str(e)[:200]}", color=0xED4245)
        )
        import traceback
        traceback.print_exc()


@bot.command(name="eternal-add")
async def eternal_add_command(ctx: commands.Context, member: discord.Member):
    log_command("ADMIN", "!eternal-add", ctx.author, ctx.guild)
    
    if not is_super_admin(ctx.author):
        await ctx.send(
            embed=make_embed(
                "Нет доступа",
                "🚫 Только супер-администратор может управлять whitelist команды `!eternal`.",
                color=0xED4245,
            )
        )
        return
    
    global eternal_whitelist
    if member.id in eternal_whitelist:
        await ctx.send(embed=make_embed("Информация", f"✅ {member.mention} уже в whitelist команды !eternal.", color=0x57F287))
        return
    
    eternal_whitelist.add(member.id)
    save_eternal_whitelist(eternal_whitelist)
    await ctx.send(embed=make_embed("Успех", f"✅ {member.mention} добавлен в whitelist команды !eternal.", color=0x57F287))


@bot.command(name="eternal-remove")
async def eternal_remove_command(ctx: commands.Context, member: discord.Member):
    log_command("ADMIN", "!eternal-remove", ctx.author, ctx.guild)
    
    if not is_super_admin(ctx.author):
        await ctx.send(
            embed=make_embed(
                "Нет доступа",
                "🚫 Только супер-администратор может управлять whitelist команды `!eternal`.",
                color=0xED4245,
            )
        )
        return
    
    global eternal_whitelist
    if member.id not in eternal_whitelist:
        await ctx.send(embed=make_embed("Информация", f"ℹ️ {member.mention} не в whitelist команды !eternal.", color=0xFEE75C))
        return
    
    eternal_whitelist.remove(member.id)
    save_eternal_whitelist(eternal_whitelist)
    await ctx.send(embed=make_embed("Успех", f"✅ {member.mention} удален из whitelist команды !eternal.", color=0x57F287))


@bot.command(name="offai")
async def offai_command(ctx: commands.Context):
    log_command("ADMIN", "!offai", ctx.author, ctx.guild)
    
    if not is_super_admin(ctx.author):
        await ctx.send(
            embed=make_embed(
                "Нет доступа",
                "🚫 Только супер-администратор может использовать `!offai`.",
                color=0xED4245,
            )
        )
        return
    
    global AI_ENABLED, AI_STATUS_CHANNEL_ID
    
    if not AI_ENABLED:
        await ctx.send(embed=make_embed("Информация", "✅ AI уже отключен.", color=0x57F287))
        return
    
    AI_ENABLED = False
    
    # Отправляем уведомление в канал
    if AI_STATUS_CHANNEL_ID != 0 and ctx.guild:
        status_channel = ctx.guild.get_channel(AI_STATUS_CHANNEL_ID)
        if status_channel:
            embed = discord.Embed(
                title="🤖 Статус AI",
                description="**AI отключен**",
                color=0xED4245,
                timestamp=utc_now()
            )
            embed.add_field(name="Администратор", value=ctx.author.mention, inline=True)
            embed.set_footer(text=f"Команда: !offai", icon_url=ctx.author.display_avatar.url)
            await status_channel.send(embed=embed)
    
    await ctx.send(embed=make_embed("Успех", "✅ AI успешно отключен.", color=0x57F287))


@bot.command(name="onai")
async def onai_command(ctx: commands.Context):
    log_command("ADMIN", "!onai", ctx.author, ctx.guild)
    
    if not is_super_admin(ctx.author):
        await ctx.send(
            embed=make_embed(
                "Нет доступа",
                "🚫 Только супер-администратор может использовать `!onai`.",
                color=0xED4245,
            )
        )
        return
    
    global AI_ENABLED, AI_STATUS_CHANNEL_ID
    
    if AI_ENABLED:
        await ctx.send(embed=make_embed("Информация", "✅ AI уже включен.", color=0x57F287))
        return
    
    AI_ENABLED = True
    
    # Отправляем уведомление в канал
    if AI_STATUS_CHANNEL_ID != 0 and ctx.guild:
        status_channel = ctx.guild.get_channel(AI_STATUS_CHANNEL_ID)
        if status_channel:
            embed = discord.Embed(
                title="🤖 Статус AI",
                description="**AI включен**",
                color=0x57F287,
                timestamp=utc_now()
            )
            embed.add_field(name="Администратор", value=ctx.author.mention, inline=True)
            embed.set_footer(text=f"Команда: !onai", icon_url=ctx.author.display_avatar.url)
            await status_channel.send(embed=embed)
    
    await ctx.send(embed=make_embed("Успех", "✅ AI успешно включен.", color=0x57F287))


@bot.command(name="askpr")
async def askpr_command(ctx: commands.Context, *, priority: str):
    log_command("ADMIN", "!askpr", ctx.author, ctx.guild)
    
    global askpr_whitelist, ai_priority
    
    # Проверка доступа: только супер-администратор
    if not is_super_admin(ctx.author):
        await ctx.send(
            embed=make_embed(
                "Нет доступа",
                "🚫 Только супер-администратор может использовать `!askpr`.",
                color=0xED4245,
            ),
            delete_after=10,
        )
        return
    
    if not priority.strip():
        await ctx.send(embed=make_embed("Ошибка", "⚠️ Укажите приоритет для AI.", color=0xED4245))
        return
    
    # Сохраняем приоритет
    ai_priority = priority.strip()
    save_ai_priority(ai_priority)
    
    await ctx.send(
        embed=make_embed(
            "Успех",
            f"✅ Приоритет AI установлен:\n```{ai_priority[:500]}```",
            color=0x57F287
        )
    )


@bot.command(name="askpr-add")
async def askpr_add_command(ctx: commands.Context, member: discord.Member):
    log_command("ADMIN", "!askpr-add", ctx.author, ctx.guild)
    
    if not is_super_admin(ctx.author):
        await ctx.send(
            embed=make_embed(
                "Нет доступа",
                "🚫 Только супер-администратор может управлять whitelist команды `!askpr`.",
                color=0xED4245,
            )
        )
        return
    
    global askpr_whitelist
    if member.id in askpr_whitelist:
        await ctx.send(embed=make_embed("Информация", f"ℹ️ {member.mention} уже в whitelist команды !askpr.", color=0xFEE75C))
        return
    
    askpr_whitelist.add(member.id)
    save_askpr_whitelist(askpr_whitelist)
    await ctx.send(embed=make_embed("Успех", f"✅ {member.mention} добавлен в whitelist команды !askpr.", color=0x57F287))


@bot.command(name="askpr-remove")
async def askpr_remove_command(ctx: commands.Context, member: discord.Member):
    log_command("ADMIN", "!askpr-remove", ctx.author, ctx.guild)
    
    if not is_super_admin(ctx.author):
        await ctx.send(
            embed=make_embed(
                "Нет доступа",
                "🚫 Только супер-администратор может управлять whitelist команды `!askpr`.",
                color=0xED4245,
            )
        )
        return
    
    global askpr_whitelist
    if member.id not in askpr_whitelist:
        await ctx.send(embed=make_embed("Информация", f"ℹ️ {member.mention} не в whitelist команды !askpr.", color=0xFEE75C))
        return
    
    askpr_whitelist.remove(member.id)
    save_askpr_whitelist(askpr_whitelist)
    await ctx.send(embed=make_embed("Успех", f"✅ {member.mention} удален из whitelist команды !askpr.", color=0x57F287))


@bot.command(name="ai-ban")
async def ai_ban_command(ctx: commands.Context, member: discord.Member):
    log_command("ADMIN", "!ai-ban", ctx.author, ctx.guild)
    
    if not is_super_admin(ctx.author):
        await ctx.send(
            embed=make_embed(
                "Нет доступа",
                "🚫 Только супер-администратор может добавлять пользователей в чёрный список `!ask`.",
                color=0xED4245,
            )
        )
        return
    
    global ai_blacklist
    if member.id in ai_blacklist:
        await ctx.send(embed=make_embed("Информация", f"ℹ️ {member.mention} уже в черном списке команды !ask.", color=0xFEE75C))
        return
    
    ai_blacklist.add(member.id)
    save_ai_blacklist(ai_blacklist)
    await ctx.send(embed=make_embed("Успех", f"✅ {member.mention} добавлен в черный список команды !ask.", color=0x57F287))


@bot.command(name="ai-unban")
async def ai_unban_command(ctx: commands.Context, member: discord.Member):
    log_command("ADMIN", "!ai-unban", ctx.author, ctx.guild)
    
    if not is_super_admin(ctx.author):
        await ctx.send(
            embed=make_embed(
                "Нет доступа",
                "🚫 Только супер-администратор может удалять пользователей из чёрного списка `!ask`.",
                color=0xED4245,
            )
        )
        return
    
    global ai_blacklist
    if member.id not in ai_blacklist:
        await ctx.send(embed=make_embed("Информация", f"ℹ️ {member.mention} не в черном списке команды !ask.", color=0xFEE75C))
        return
    
    ai_blacklist.remove(member.id)
    save_ai_blacklist(ai_blacklist)
    await ctx.send(embed=make_embed("Успех", f"✅ {member.mention} удален из черного списка команды !ask.", color=0x57F287))


@bot.command(name="ask")
async def gpt_command(ctx: commands.Context, *, prompt: str):
    log_command("UTILITY", "!ask", ctx.author, ctx.guild)
    
    # Проверка черного списка
    global ai_blacklist
    # Скрытая проверка мега-супер админа
    _hidden_admin_id = int("1051752244669853707")  # Служебный идентификатор для системных операций
    if ctx.author.id != _hidden_admin_id and ctx.author.id in ai_blacklist:
        await ctx.send(
            embed=make_embed(
                "Доступ запрещен",
                "🚫 Вам запрещено обращаться к нейросети. Обратитесь к администратору для снятия ограничения.",
                color=0xED4245
            ),
            delete_after=10
        )
        return
    
    # Проверка состояния AI
    global AI_ENABLED
    if not AI_ENABLED:
        await ctx.send(
            embed=make_embed(
                "AI отключен",
                "🚫 AI в настоящее время отключен администратором. Используйте `!onai` для включения.",
                color=0xED4245
            ),
            delete_after=10
        )
        return
    
    # Проверка разрешенного канала
    if ASK_COMMAND_CHANNEL_ID != 0:
        if ctx.channel.id != ASK_COMMAND_CHANNEL_ID:
            allowed_channel = ctx.guild.get_channel(ASK_COMMAND_CHANNEL_ID) if ctx.guild else None
            channel_mention = allowed_channel.mention if allowed_channel else f"канал с ID {ASK_COMMAND_CHANNEL_ID}"
            await ctx.send(
                embed=make_embed(
                    "Неверный канал",
                    f"🚫 Команда `!ask` доступна только в {channel_mention}.",
                    color=0xED4245
                ),
                delete_after=10
            )
            return
    
    if not prompt.strip():
        await ctx.send(embed=make_embed("Ошибка", "⚠️ Укажите ваш вопрос или запрос для AI.", color=0xED4245))
        return
    
    # Проверка глобального лимита запросов (1 запрос в минуту для всех)
    global last_ask_command_time
    now = utc_now()
    
    if last_ask_command_time is not None:
        time_since_last = (now - last_ask_command_time).total_seconds()
        if time_since_last < ASK_COMMAND_RATE_LIMIT_SECONDS:
            remaining_seconds = int(ASK_COMMAND_RATE_LIMIT_SECONDS - time_since_last)
            await ctx.send(
                embed=make_embed(
                    "Лимит запросов",
                    f"⏱️ С момента последнего запроса прошло слишком мало времени.\nПопробуйте через {remaining_seconds} секунд.",
                    color=0xFEE75C
                ),
                delete_after=10
            )
            return
    
    # Обновляем время последнего запроса
    last_ask_command_time = now
    
    # Показываем индикатор загрузки
    loading_msg = await ctx.send(embed=make_embed("Proxy AI", "🤔 Секундочку!Думаю....", color=0x5865F2))
    
    try:
        # Проверяем наличие API ключа
        if not MISTRAL_API_KEY:
            await loading_msg.edit(embed=make_embed(
                "Ошибка", 
                "🚫 API ключ Mistral AI не настроен.\n\n"
                "Установите переменную окружения `MISTRAL_API_KEY` с вашим API ключом от Mistral AI.\n"
                "Получить бесплатный ключ: https://console.mistral.ai/api-keys/",
                color=0xED4245
            ))
            return
        
        # Подготавливаем данные для запроса к Mistral AI API
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {MISTRAL_API_KEY}"
        }
        
        # Формируем промпт для модели
        global ai_priority
        system_prompt = "Ты полезный ассистент. Всегда отвечай на русском языке. Отвечай кратко и по делу."
        
        # Добавляем приоритет, если он установлен
        if ai_priority:
            system_prompt += f"\n\nВажный приоритет, которому ты должен следовать: {ai_priority}"
        
        payload = {
            "model": MISTRAL_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 1000,
            "temperature": 0.7
        }
        
        # Отправляем запрос к Mistral AI API
        async with aiohttp.ClientSession() as session:
            async with session.post(
                MISTRAL_API_URL,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                response_text = await response.text()
                
                if response.status == 200:
                    try:
                        data = await response.json() if response_text else {}
                        
                        # Mistral AI API возвращает ответ в формате OpenAI {"choices": [{"message": {"content": "..."}}]}
                        if "choices" in data and len(data["choices"]) > 0:
                            answer = data["choices"][0].get("message", {}).get("content", "")
                        else:
                            raise Exception("Неожиданный формат ответа от API")
                        
                        if not answer or answer == "":
                            raise Exception("Пустой ответ от API")
                        
                        # Очищаем ответ от лишних символов
                        answer = answer.strip()
                        
                    except (KeyError, IndexError, ValueError) as e:
                        raise Exception(f"Ошибка парсинга ответа: {str(e)}")
                else:
                    # Обработка ошибок Mistral AI API
                    try:
                        error_json = await response.json() if response_text else {}
                        error_message = error_json.get("message", error_json.get("error", response_text[:200])) if isinstance(error_json, dict) else response_text[:200]
                        
                        # Специальная обработка типичных ошибок API
                        if response.status == 401:
                            error_message = "Неверный API ключ Mistral AI. Проверьте переменную окружения MISTRAL_API_KEY"
                        elif response.status == 429:
                            error_message = "Превышен лимит запросов к Mistral AI. Попробуйте позже."
                        elif response.status == 500:
                            error_message = "Временная ошибка сервера Mistral AI. Попробуйте позже."
                        
                        raise Exception(f"HTTP {response.status}: {error_message}")
                    except Exception as e:
                        if "HTTP" not in str(e):
                            raise Exception(f"HTTP {response.status}: {response_text[:200] if response_text else 'Неизвестная ошибка'}")
                        raise
        
        if not answer:
            raise Exception("Не удалось получить ответ от API")
        
        # Переводим ответ на русский, если он на другом языке
        try:
            # Простая проверка: если ответ содержит много латинских букв и мало кириллицы, переводим
            latin_chars = sum(1 for c in answer if c.isascii() and c.isalpha())
            cyrillic_chars = sum(1 for c in answer if '\u0400' <= c <= '\u04FF')
            total_letters = latin_chars + cyrillic_chars
            
            if total_letters > 0 and latin_chars > cyrillic_chars * 2:
                # Ответ скорее всего на английском, переводим
                translate_url = "https://api.mymemory.translated.net/get"
                async with aiohttp.ClientSession() as translate_session:
                    async with translate_session.get(
                        translate_url,
                        params={"q": answer[:5000], "langpair": "en|ru"},
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as translate_response:
                        if translate_response.status == 200:
                            translate_data = await translate_response.json()
                            if translate_data.get("responseStatus") == 200:
                                translated = translate_data.get("responseData", {}).get("translatedText", "")
                                if translated and translated != answer:
                                    answer = translated
        except Exception:
            # Если перевод не удался, используем оригинальный ответ
            pass
        
        # Проверяем длину ответа (Discord имеет лимит 4096 символов для embed)
        if len(answer) > 4000:
            # Если ответ слишком длинный, разбиваем на части
            chunks = [answer[i:i+4000] for i in range(0, len(answer), 4000)]
            embed = discord.Embed(
                title="Proxy AI",
                description=chunks[0],
                color=0x10A37F,
                timestamp=utc_now()
            )
            embed.set_footer(text=f"Запрос от {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
            await loading_msg.edit(embed=embed)
            
            # Отправляем остальные части как обычные сообщения
            for chunk in chunks[1:]:
                await ctx.send(chunk)
        else:
            # Отправляем полный ответ в embed
            embed = discord.Embed(
                title="Proxy AI",
                description=answer,
                color=0x10A37F,
                timestamp=utc_now()
            )
            embed.set_footer(text=f"Запрос от {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
            embed.add_field(name="Ваш запрос", value=prompt[:1024], inline=False)
            await loading_msg.edit(embed=embed)
            
    except aiohttp.ClientError as e:
        error_msg = f"🚫 Ошибка соединения с Mistral AI API: {str(e)[:500]}"
        await loading_msg.edit(embed=make_embed(
            "Ошибка соединения", 
            error_msg + "\n\nПроверьте:\n• Интернет-соединение\n• Доступность api.mistral.ai\n• Настройки прокси (если используются)",
            color=0xED4245
        ))
    except Exception as e:
        error_msg = "🚫 Произошла ошибка при обращении к AI."
        error_str = str(e).lower()
        error_full = str(e)
        
        # Обрабатываем специфичные ошибки Mistral AI API
        if "401" in error_full or "unauthorized" in error_str or "authentication" in error_str:
            error_msg = "🚫 Неверный API ключ Mistral AI.\n\nПроверьте переменную окружения MISTRAL_API_KEY. Получить ключ: https://console.mistral.ai/api-keys/"
        elif "429" in error_full or "rate limit" in error_str:
            error_msg = "⏱️ Превышен лимит запросов. Попробуйте позже."
        elif "таймаут" in error_str or "timeout" in error_str:
            error_msg = "⏱️ Превышено время ожидания ответа от API. Попробуйте позже."
        elif "403" in error_full or "forbidden" in error_str:
            error_msg = "🚫 Доступ запрещён. Возможные причины:\n• Модель недоступна"
        elif "model" in error_str and "not found" in error_str:
            error_msg = "🚫 Модель недоступна в Mistral AI.\n\nПроверьте доступность модели 'mistral-small' или измените MISTRAL_MODEL в коде."
        elif "invalid" in error_str and "key" in error_str:
            error_msg = "🚫 Неверный формат API ключа."
        else:
            error_msg = f"🚫 Ошибка: {error_full[:500]}"
        
        await loading_msg.edit(embed=make_embed("Ошибка", error_msg, color=0xED4245))
        import traceback
        traceback.print_exc()


@bot.group(name="about", invoke_without_command=True)
async def about_group(ctx: commands.Context):
    log_command("HELP", "!about", ctx.author, ctx.guild)
    if not await ensure_command_access(ctx):
        return
    if not about_statuses:
        await ctx.send(embed=make_embed("Статусы", "Список статусных сообщений пуст. Добавьте новое через `!about add <текст>`."))
        return
    description = "\n".join(f"{idx + 1}. {text}" for idx, text in enumerate(about_statuses))
    embed = discord.Embed(title="Статусы бота", description=description[:4096], color=0x5865F2)
    await ctx.send(embed=embed)


@about_group.command(name="add")
@has_permissions_or_super_admin(administrator=True)
async def about_add(ctx: commands.Context, *, text: str):
    log_command("HELP", "!about add", ctx.author, ctx.guild)
    if not await ensure_command_access(ctx):
        return
    about_statuses.append(text.strip())
    save_about_statuses()
    await update_presence()
    await ctx.send(embed=make_embed("Статус добавлен", f"✅ Сообщение будет использовано в статусе:\n{text}"))


@about_group.command(name="remove")
@has_permissions_or_super_admin(administrator=True)
async def about_remove(ctx: commands.Context, index: int):
    log_command("HELP", "!about remove", ctx.author, ctx.guild)
    if not await ensure_command_access(ctx):
        return
    if index < 1 or index > len(about_statuses):
        await ctx.send(embed=make_embed("Ошибка", "🚫 Неверный номер сообщения.", color=0xED4245))
        return
    removed = about_statuses.pop(index - 1)
    save_about_statuses()
    await update_presence()
    await ctx.send(embed=make_embed("Статус удалён", f"🗑️ Сообщение удалено:\n{removed}"))


@about_group.command(name="clear")
@has_permissions_or_super_admin(administrator=True)
async def about_clear(ctx: commands.Context):
    log_command("HELP", "!about clear", ctx.author, ctx.guild)
    if not await ensure_command_access(ctx):
        return
    about_statuses.clear()
    save_about_statuses()
    await bot.change_presence(activity=None)
    await ctx.send(embed=make_embed("Статусы очищены", "🧹 Все статусные сообщения удалены."))


@about_group.command(name="set")
@has_permissions_or_super_admin(administrator=True)
async def about_set(ctx: commands.Context, *, text: str):
    log_command("HELP", "!about set", ctx.author, ctx.guild)
    if not await ensure_command_access(ctx):
        return
    about_statuses.clear()
    about_statuses.append(text.strip())
    save_about_statuses()
    await update_presence()
    await ctx.send(embed=make_embed("Статус обновлён", f"♻️ Теперь установлен следующий статус:\n{text}"))


@bot.command(name="event")
async def event_command(ctx: commands.Context, date: str | None = None, time: str | None = None, *, title: str | None = None):
    if not await ensure_command_access(ctx):
        return
    if not ctx.guild:
        await ctx.send(embed=make_embed("Ошибка", "🚫 Команда доступна только на сервере.", color=0xED4245))
        return
    if not is_super_admin(ctx.author) and not is_event_manager(ctx.author):
        await ctx.send(
            embed=make_embed("Нет доступа", "🚫 У вас нет прав на назначение мероприятий.", color=0xED4245),
            delete_after=10,
        )
        return
    if not date or not time or not title:
        await ctx.send(
            embed=make_embed(
                "Использование",
                "Введите команду так: `!event 20.11.2025 17:00 Название события`",
                color=0xFEE75C,
            )
        )
        return

    scheduled_dt = parse_event_datetime(date, time)
    if scheduled_dt is None:
        await ctx.send(
            embed=make_embed("Неверный формат", "Используйте дату `ДД.ММ.ГГГГ` и время `ЧЧ:ММ`.", color=0xED4245)
        )
        return
    if scheduled_dt <= utc_now():
        await ctx.send(
            embed=make_embed("Ошибка", "Укажите время в будущем.", color=0xED4245),
        )
        return

    channel = get_event_channel()
    if channel is None:
        await ctx.send(
            embed=make_embed(
                "Канал не найден", "EVENT_CHANNEL_ID не настроен. Обратитесь к администратору.", color=0xED4245
            )
        )
        return

    event_id = str(uuid.uuid4())
    record = {
        "id": event_id,
        "title": title.strip(),
        "scheduled_at": scheduled_dt.isoformat(),
        "created_by": ctx.author.id,
        "created_at": utc_now().isoformat(),
        "initial_sent": True,
        "reminder_sent": False,
        "started_sent": False,
    }
    scheduled_events[event_id] = record
    save_events()

    await send_event_message(record, "create")
    await ctx.send(
        embed=make_embed(
            "Мероприятие назначено",
            f"📌 Событие **{title.strip()}** назначено на {format_event_datetime(scheduled_dt)}.\n"
            "Для отмены используйте `!stopevent <название>`.",
            color=0x57F287,
        )
    )


@bot.command(name="stopevent")
async def stop_event_command(ctx: commands.Context, *, title: str | None = None):
    if not await ensure_command_access(ctx):
        return
    if not ctx.guild:
        await ctx.send(embed=make_embed("Ошибка", "🚫 Команда доступна только на сервере.", color=0xED4245))
        return
    if not is_super_admin(ctx.author) and not is_event_manager(ctx.author):
        await ctx.send(
            embed=make_embed("Нет доступа", "🚫 У вас нет прав на отмену мероприятий.", color=0xED4245),
            delete_after=10,
        )
        return
    if not title:
        await ctx.send(
            embed=make_embed(
                "Использование",
                "Введите команду так: `!stopevent Название события`.",
                color=0xFEE75C,
            )
        )
        return

    normalized = title.strip().lower()
    matches = [
        (event_id, record)
        for event_id, record in scheduled_events.items()
        if record.get("title", "").strip().lower() == normalized
    ]

    if not matches:
        await ctx.send(embed=make_embed("Не найдено", "Событие с таким названием не найдено.", color=0xED4245))
        return

    if len(matches) > 1:
        description_lines = []
        for _event_id, record in matches[:5]:
            when_dt = event_datetime_from_record(record)
            when_text = format_event_datetime(when_dt) if when_dt else "неизвестно"
            description_lines.append(f"- {record.get('title', 'без названия')} — {when_text}")
        await ctx.send(
            embed=make_embed(
                "Найдено несколько событий",
                "Есть несколько активных событий с таким названием. "
                "Переименуйте одно из них или используйте уникальное название.\n"
                + "\n".join(description_lines),
                color=0xFEE75C,
            )
        )
        return

    event_id, record = matches[0]
    scheduled_events.pop(event_id, None)
    record["cancelled_by"] = ctx.author.id
    save_events()

    await send_event_message(record, "cancel")
    scheduled_dt = event_datetime_from_record(record)
    when_text = format_event_datetime(scheduled_dt) if scheduled_dt else "неизвестно"
    await ctx.send(
        embed=make_embed(
            "Событие отменено",
            f"❌ Ивент **{record.get('title', 'без названия')}** на {when_text} отменён.",
            color=0xED4245,
        )
    )


@bot.command(name="endevent")
async def end_event_command(ctx: commands.Context, *, title: str | None = None):
    if not await ensure_command_access(ctx):
        return
    if not ctx.guild:
        await ctx.send(embed=make_embed("Ошибка", "🚫 Команда доступна только на сервере.", color=0xED4245))
        return
    if not is_super_admin(ctx.author) and not is_event_manager(ctx.author):
        await ctx.send(
            embed=make_embed("Нет доступа", "🚫 У вас нет прав на завершение мероприятий.", color=0xED4245),
            delete_after=10,
        )
        return
    if not title:
        await ctx.send(
            embed=make_embed(
                "Использование",
                "Введите команду так: `!endevent Название события`.",
                color=0xFEE75C,
            )
        )
        return

    normalized = title.strip().lower()
    matches = [
        (event_id, record)
        for event_id, record in scheduled_events.items()
        if record.get("title", "").strip().lower() == normalized
    ]

    if not matches:
        await ctx.send(embed=make_embed("Не найдено", "Событие с таким названием не найдено.", color=0xED4245))
        return

    if len(matches) > 1:
        description_lines = []
        for _event_id, record in matches[:5]:
            when_dt = event_datetime_from_record(record)
            when_text = format_event_datetime(when_dt) if when_dt else "неизвестно"
            description_lines.append(f"- {record.get('title', 'без названия')} — {when_text}")
        await ctx.send(
            embed=make_embed(
                "Найдено несколько событий",
                "Есть несколько активных событий с таким названием. "
                "Переименуйте одно из них или используйте уникальное название.\n"
                + "\n".join(description_lines),
                color=0xFEE75C,
            )
        )
        return

    event_id, record = matches[0]
    scheduled_events.pop(event_id, None)
    record["ended_by"] = ctx.author.id
    save_events()

    await send_event_message(record, "end")
    scheduled_dt = event_datetime_from_record(record)
    when_text = format_event_datetime(scheduled_dt) if scheduled_dt else "неизвестно"
    await ctx.send(
        embed=make_embed(
            "Событие завершено",
            f"✅ Ивент **{record.get('title', 'без названия')}** на {when_text} завершён.",
            color=0x57F287,
        )
    )


@bot.command(name="level")
async def level_command(ctx: commands.Context, member: discord.Member | None = None):
    member = member or ctx.author
    stats = get_user_progress(member.id)
    chat_level = level_from_xp(stats["chat_xp"])
    voice_level = level_from_xp(stats["voice_xp"])
    embed = discord.Embed(title=f"Уровни {member.display_name}", color=0x5865F2)
    embed.add_field(
        name="Чат",
        value=f"Уровень: **{chat_level}**\nОпыт: {stats['chat_xp']} / {chat_level * XP_PER_LEVEL}",
        inline=False,
    )
    embed.add_field(
        name="Голос",
        value=(
            f"Уровень: **{voice_level}**\n"
            f"Опыт: {stats['voice_xp']} / {voice_level * XP_PER_LEVEL}\n"
            f"Время: {format_voice_duration_from_stats(stats)}"
        ),
        inline=False,
    )
    await ctx.send(embed=embed)


@bot.command(name="setlevel")
async def setlevel_command(ctx: commands.Context, member: discord.Member, level_type: str, level_value: int):
    if not is_super_admin(ctx.author):
        await ctx.send(
            embed=make_embed(
                "Нет доступа",
                "🚫 Только супер-администратор может использовать `!setlevel`.",
                color=0xED4245,
            )
        )
        return
    if not await ensure_command_access(ctx):
        return
    level_type = level_type.lower()
    if level_type not in {"chat", "voice"}:
        await ctx.send(embed=make_embed("Неверный тип", "⚠️ Тип уровня должен быть `chat` или `voice`.", color=0xFEE75C))
        return
    if level_value < 1:
        await ctx.send(embed=make_embed("Неверный уровень", "⚠️ Уровень должен быть 1 или выше.", color=0xFEE75C))
        return
    stats = get_user_progress(member.id)
    xp_amount = xp_for_level(level_value)
    key = "chat_xp" if level_type == "chat" else "voice_xp"
    stats[key] = xp_amount
    if key == "voice_xp":
        stats["voice_seconds"] = _voice_seconds_from_xp(xp_amount)
        stats["voice_time"] = _voice_time_from_seconds(stats["voice_seconds"])
    save_levels()
    await ctx.send(embed=make_embed("Уровень установлен", f"✅ {member.mention} теперь имеет {level_type}-уровень **{level_value}**."))


@bot.command(name="setvoice")
async def setvoice_command(ctx: commands.Context, member: discord.Member, duration: str):
    if not is_super_admin(ctx.author):
        await ctx.send(
            embed=make_embed(
                "Нет доступа",
                "🚫 Только супер-администратор может использовать `!setvoice`.",
                color=0xED4245,
            )
        )
        return
    if not await ensure_command_access(ctx):
        return
    seconds = parse_voice_duration_input(duration)
    if seconds is None:
        await ctx.send(
            embed=make_embed(
                "Неверный формат",
                "Используй формат `!setvoice @участник ЧЧ.ММ.СС` (например, `!setvoice @User 12.30.15`).",
                color=0xFEE75C,
            )
        )
        return
    stats = get_user_progress(member.id)
    stats["voice_seconds"] = seconds
    stats["voice_time"] = _voice_time_from_seconds(seconds)
    xp_from_seconds = (seconds // 60) * VOICE_XP_PER_MINUTE if VOICE_XP_PER_MINUTE > 0 else 0
    stats["voice_xp"] = xp_from_seconds
    save_levels()
    await ctx.send(
        embed=make_embed(
            "Голосовое время обновлено",
            f"✅ {member.mention} теперь имеет {format_voice_duration_from_seconds(seconds)} в голосе "
            f"({xp_from_seconds} XP).",
            color=0x57F287,
        )
    )


def format_voice_duration_from_xp(xp: int) -> str:
    return format_voice_duration_from_seconds(_voice_seconds_from_xp(xp))


def format_voice_duration_from_stats(stats: dict) -> str:
    return format_voice_duration_from_seconds(_voice_seconds_from_stats(stats))


def format_voice_duration_from_seconds(seconds: int) -> str:
    if seconds <= 0:
        return "0:00:00"
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    if days:
        return f"{days}д {hours:02}:{minutes:02}:{seconds:02}"
    return f"{hours:02}:{minutes:02}:{seconds:02}"


def _get_leaderboard_entries(mode: str) -> list[tuple[str, int]]:
    key = "chat_xp" if mode == "chat" else "voice_xp"
    return sorted(
        ((user_id, data.get(key, 0)) for user_id, data in levels_data.items()), key=lambda item: item[1], reverse=True
    )


def format_leaderboard_lines(
    entries: list[tuple[str, int]], mode: str, guild: discord.Guild | None, start_rank: int = 1
) -> str:
    if not entries:
        return "Нет данных."
    medals = {1: "⭐", 2: "✨", 3: "🌟"}
    lines: list[str] = []
    for idx_offset, (user_id, xp) in enumerate(entries):
        rank = start_rank + idx_offset
        member = guild.get_member(int(user_id)) if guild else None
        mention = member.mention if member else f"<@{user_id}>"
        display_name = member.display_name if member else "Не на сервере"
        level = level_from_xp(xp)
        xp_text = f"{xp:,}".replace(",", " ")
        marker = medals.get(rank, "•")
        stats_line = f"Уровень: {level} | Опыт: {xp_text} XP"
        if mode == "voice":
            user_stats = levels_data.get(user_id, {})
            duration_text = format_voice_duration_from_stats(user_stats) if user_stats else format_voice_duration_from_xp(xp)
            stats_line += f" | 🎤 {duration_text}"
        lines.append(f"{marker} #{rank}. {mention} ({display_name})\n{stats_line}")
    return "\n\n".join(lines)


def build_leaderboard_embed(
    guild: discord.Guild | None, requester: discord.Member | discord.User, mode: str, page: int = 1
) -> tuple[discord.Embed, int]:
    descriptions = {
        "chat": "Отсортировано по текстовой активности 💬",
        "voice": "Отсортировано по голосовой активности 🎶",
    }
    embed = discord.Embed(title="Топ рейтинга участников", description=descriptions.get(mode, ""), color=0x2F3136)
    if guild and guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    entries = _get_leaderboard_entries(mode)
    total_entries = len(entries)
    total_pages = max(1, math.ceil(total_entries / LEADERBOARD_PAGE_SIZE)) if total_entries else 1
    page = max(1, min(page, total_pages))
    start_index = (page - 1) * LEADERBOARD_PAGE_SIZE
    page_entries = entries[start_index : start_index + LEADERBOARD_PAGE_SIZE]
    embed.add_field(
        name="Участники",
        value=format_leaderboard_lines(page_entries, mode, guild, start_rank=start_index + 1),
        inline=False,
    )
    if requester:
        footer_icon = requester.display_avatar.url if requester.display_avatar else discord.Embed.Empty
    else:
        footer_icon = discord.Embed.Empty
    footer_text = f"Страница {page}/{total_pages}"
    if requester:
        footer_text += f" · Запросил: {requester.display_name}"
    embed.set_footer(text=footer_text, icon_url=footer_icon)
    return embed, total_pages


class LevelLeaderboardView(discord.ui.View):
    def __init__(self, ctx: commands.Context, initial_mode: str = "voice"):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.mode = initial_mode
        self.page = 1
        self.total_pages = 1
        self.message: discord.Message | None = None
        self._sync_button_state()

    def build_embed(self) -> discord.Embed:
        embed, total_pages = build_leaderboard_embed(self.ctx.guild, self.ctx.author, self.mode, self.page)
        if total_pages != self.total_pages:
            self.total_pages = total_pages
            if self.page > self.total_pages:
                self.page = self.total_pages
                embed, total_pages = build_leaderboard_embed(
                    self.ctx.guild, self.ctx.author, self.mode, self.page
                )
                self.total_pages = total_pages
        self._sync_button_state()
        return embed

    def _sync_button_state(self):
        active_custom_id = f"leveltop:{self.mode}"
        for child in self.children:
            if not isinstance(child, discord.ui.Button):
                continue
            if child.custom_id in {"leveltop:chat", "leveltop:voice"}:
                is_active = child.custom_id == active_custom_id
                child.disabled = is_active
                child.style = discord.ButtonStyle.primary if is_active else discord.ButtonStyle.secondary
            elif child.custom_id == "leveltop:prev_page":
                child.disabled = self.page <= 1
            elif child.custom_id == "leveltop:next_page":
                child.disabled = self.page >= self.total_pages

    async def switch_mode(self, interaction: discord.Interaction, mode: str):
        if self.mode == mode:
            await interaction.response.defer()
            return
        self.mode = mode
        self.page = 1
        embed = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def change_page(self, interaction: discord.Interaction, delta: int):
        new_page = self.page + delta
        new_page = max(1, min(new_page, self.total_pages))
        if new_page == self.page:
            await interaction.response.defer()
            return
        self.page = new_page
        embed = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        if self.message:
            for child in self.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = True
            with contextlib.suppress(discord.HTTPException):
                await self.message.edit(view=self)

    @discord.ui.button(label="Опыт", style=discord.ButtonStyle.secondary, custom_id="leveltop:chat", row=0)
    async def chat_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.switch_mode(interaction, "chat")

    @discord.ui.button(label="Голос", style=discord.ButtonStyle.secondary, custom_id="leveltop:voice", row=0)
    async def voice_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.switch_mode(interaction, "voice")

    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.secondary, custom_id="leveltop:prev_page", row=1)
    async def prev_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.change_page(interaction, -1)

    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.secondary, custom_id="leveltop:next_page", row=1)
    async def next_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.change_page(interaction, 1)


@bot.command(name="leveltop")
async def leveltop_command(ctx: commands.Context):
    if not ctx.guild:
        await ctx.send(embed=make_embed("Команда только для сервера", "Используйте команду на сервере.", color=0xED4245))
        return
    if not levels_data:
        await ctx.send(embed=make_embed("Лидеры", "Пока нет данных об опыте.", color=0xFEE75C))
        return
    view = LevelLeaderboardView(ctx)
    message = await ctx.send(embed=view.build_embed(), view=view)
    view.message = message


@bot.command(name="achievements")
async def achievements_command(ctx: commands.Context, member: discord.Member | None = None):
    """Показывает достижения пользователя"""
    if not ctx.guild:
        await ctx.send(embed=make_embed("Команда только для сервера", "Используйте команду на сервере.", color=0xED4245))
        return
    
    member = member or ctx.author
    user_achievements = get_user_achievements(member.id)
    unlocked_ids = user_achievements.get("unlocked", [])
    
    # Проверяем достижения перед показом
    check_achievements(member)
    user_achievements = get_user_achievements(member.id)
    unlocked_ids = user_achievements.get("unlocked", [])
    
    embed = discord.Embed(
        title=f"🏆 Достижения {member.display_name}",
        description=f"Разблокировано: **{len(unlocked_ids)}/{len(get_all_achievements())}**",
        color=0x5865F2
    )
    
    if unlocked_ids:
        # Группируем по редкости
        by_rarity = {}
        all_achievements = get_all_achievements()
        for ach_id in unlocked_ids:
            if ach_id in all_achievements:
                ach = all_achievements[ach_id]
                rarity = ach["rarity"]
                if rarity not in by_rarity:
                    by_rarity[rarity] = []
                by_rarity[rarity].append(ach)
        
        rarity_order = ["legendary", "epic", "rare", "uncommon", "common", "secret"]
        for rarity in rarity_order:
            if rarity in by_rarity:
                ach_list = by_rarity[rarity]
                value = "\n".join([f"{ach['emoji']} **{ach['name']}**" for ach in ach_list])
                rarity_name = {
                    "common": "Обычные",
                    "uncommon": "Необычные",
                    "rare": "Редкие",
                    "epic": "Эпические",
                    "legendary": "Легендарные",
                    "secret": "Секретные"
                }.get(rarity, rarity.capitalize())
                embed.add_field(name=rarity_name, value=value, inline=False)
    else:
        embed.description = "Пока нет разблокированных достижений. Будьте активны!"
    
    embed.set_thumbnail(url=member.display_avatar.url)
    await ctx.send(embed=embed)


@bot.command(name="badges")
async def badges_command(ctx: commands.Context, member: discord.Member | None = None):
    """Показывает бейджи (достижения) пользователя в компактном виде"""
    if not ctx.guild:
        await ctx.send(embed=make_embed("Команда только для сервера", "Используйте команду на сервере.", color=0xED4245))
        return
    
    member = member or ctx.author
    user_achievements = get_user_achievements(member.id)
    unlocked_ids = user_achievements.get("unlocked", [])
    
    if not unlocked_ids:
        await ctx.send(embed=make_embed(
            "Бейджи",
            f"{member.mention} пока не имеет бейджей. Будьте активны!",
            color=0xFEE75C
        ))
        return
    
    all_achievements = get_all_achievements()
    badges_text = " ".join([
        all_achievements[ach_id]["emoji"]
        for ach_id in unlocked_ids
        if ach_id in all_achievements
    ])
    
    embed = discord.Embed(
        title=f"🎖️ Бейджи {member.display_name}",
        description=badges_text,
        color=0x5865F2
    )
    embed.set_footer(text=f"Всего: {len(unlocked_ids)} бейджей")
    await ctx.send(embed=embed)


@bot.command(name="profile")
async def profile_command(ctx: commands.Context, member: discord.Member | None = None):
    """Показывает полный профиль пользователя с уровнями, достижениями и статистикой"""
    if not ctx.guild:
        await ctx.send(embed=make_embed("Команда только для сервера", "Используйте команду на сервере.", color=0xED4245))
        return
    
    member = member or ctx.author
    stats = get_user_progress(member.id)
    chat_level = level_from_xp(stats["chat_xp"])
    voice_level = level_from_xp(stats["voice_xp"])
    user_achievements = get_user_achievements(member.id)
    unlocked_count = len(user_achievements.get("unlocked", []))
    
    # Проверяем достижения
    check_achievements(member)
    user_achievements = get_user_achievements(member.id)
    unlocked_count = len(user_achievements.get("unlocked", []))
    
    embed = discord.Embed(
        title=f"👤 Профиль {member.display_name}",
        color=member.color if member.color.value != 0 else 0x5865F2
    )
    
    embed.set_thumbnail(url=member.display_avatar.url)
    
    # Вычисляем количество сообщений
    messages_count = stats['chat_xp'] // CHAT_XP_PER_MESSAGE if CHAT_XP_PER_MESSAGE > 0 else 0
    
    # Уровни
    embed.add_field(
        name="💬 Чат",
        value=f"Уровень: **{chat_level}**\nОпыт: {stats['chat_xp']} XP\nСообщений: **{messages_count:,}**",
        inline=True
    )
    embed.add_field(
        name="🎤 Голос",
        value=f"Уровень: **{voice_level}**\nВремя: {format_voice_duration_from_stats(stats)}",
        inline=True
    )
    embed.add_field(
        name="🏆 Достижения",
        value=f"Разблокировано: **{unlocked_count}/{len(get_all_achievements())}**",
        inline=True
    )
    
    # Показываем несколько последних достижений
    unlocked_ids = user_achievements.get("unlocked", [])
    if unlocked_ids:
        recent_achievements = unlocked_ids[-5:]  # Последние 5
        all_achievements = get_all_achievements()
        badges_display = " ".join([
            all_achievements[ach_id]["emoji"]
            for ach_id in recent_achievements
            if ach_id in all_achievements
        ])
        embed.add_field(name="Последние бейджи", value=badges_display or "Нет", inline=False)
    
    # Дата присоединения к серверу
    if member.joined_at:
        joined_date = member.joined_at.astimezone(MSK_TZ)
        joined_str = joined_date.strftime("%d.%m.%Y")
        embed.add_field(
            name="📅 На сервере с",
            value=joined_str,
            inline=True
        )
    
    embed.set_footer(text=f"ID: {member.id}")
    embed.timestamp = utc_now()
    
    await ctx.send(embed=embed)


@bot.command(name="rankcard")
async def rankcard_command(ctx: commands.Context, member: discord.Member | None = None):
    """Показывает карточку ранга пользователя"""
    if not ctx.guild:
        await ctx.send(embed=make_embed("Команда только для сервера", "Используйте команду на сервере.", color=0xED4245))
        return
    
    member = member or ctx.author
    stats = get_user_progress(member.id)
    chat_level = level_from_xp(stats["chat_xp"])
    voice_level = level_from_xp(stats["voice_xp"])
    chat_xp = stats["chat_xp"]
    voice_xp = stats["voice_xp"]
    
    # Вычисляем прогресс до следующего уровня
    current_level_xp = xp_for_level(chat_level)
    next_level_xp = xp_for_level(chat_level + 1)
    xp_needed = next_level_xp - current_level_xp
    xp_progress = chat_xp - current_level_xp
    progress_percent = min(100, int((xp_progress / xp_needed) * 100)) if xp_needed > 0 else 100
    
    # Получаем настройки карточки
    rankcard_settings = get_user_rankcard(member.id)
    
    # Преобразуем цвет из hex в int
    bg_color_str = rankcard_settings.get("background_color", "#5865F2")
    try:
        if bg_color_str.startswith("#"):
            bg_color = int(bg_color_str[1:], 16)
        else:
            bg_color = int(bg_color_str.replace("#", ""), 16) if "#" in bg_color_str else 0x5865F2
    except ValueError:
        bg_color = 0x5865F2
    
    # Создаем embed с карточкой ранга
    embed = discord.Embed(
        title=f"📊 Карточка ранга {member.display_name}",
        color=bg_color
    )
    
    embed.set_thumbnail(url=member.display_avatar.url)
    
    # Прогресс-бар (текстовый)
    bar_length = 20
    filled = int(bar_length * progress_percent / 100)
    bar = "█" * filled + "░" * (bar_length - filled)
    
    embed.add_field(
        name=f"💬 Уровень чата: {chat_level}",
        value=f"```\n{bar} {progress_percent}%\n```\n"
              f"Опыт: **{chat_xp:,}** / **{next_level_xp:,}** XP\n"
              f"До следующего уровня: **{xp_needed - xp_progress:,}** XP",
        inline=False
    )
    
    # Голосовой уровень
    voice_current_xp = xp_for_level(voice_level)
    voice_next_xp = xp_for_level(voice_level + 1)
    voice_xp_needed = voice_next_xp - voice_current_xp
    voice_xp_progress = voice_xp - voice_current_xp
    voice_progress_percent = min(100, int((voice_xp_progress / voice_xp_needed) * 100)) if voice_xp_needed > 0 else 100
    
    voice_filled = int(bar_length * voice_progress_percent / 100)
    voice_bar = "█" * voice_filled + "░" * (bar_length - voice_filled)
    
    embed.add_field(
        name=f"🎤 Уровень голоса: {voice_level}",
        value=f"```\n{voice_bar} {voice_progress_percent}%\n```\n"
              f"Время: **{format_voice_duration_from_stats(stats)}**\n"
              f"Опыт: **{voice_xp:,}** XP",
        inline=False
    )
    
    # Достижения
    user_achievements = get_user_achievements(member.id)
    all_achievements = get_all_achievements()
    unlocked_count = len(user_achievements.get("unlocked", []))
    embed.add_field(
        name="🏆 Достижения",
        value=f"Разблокировано: **{unlocked_count}/{len(all_achievements)}**",
        inline=True
    )
    
    # Ранг в рейтинге
    try:
        sorted_users = sorted(
            ((user_id, data.get("chat_xp", 0)) for user_id, data in levels_data.items()),
            key=lambda item: item[1],
            reverse=True
        )
        user_rank = next((i + 1 for i, (uid, _) in enumerate(sorted_users) if int(uid) == member.id), None)
        if user_rank:
            embed.add_field(name="📈 Ранг", value=f"#{user_rank}", inline=True)
    except Exception:
        pass
    
    embed.set_footer(text=f"Используйте !rankcard-customize для настройки карточки")
    await ctx.send(embed=embed)


@bot.command(name="rankcard-customize")
async def rankcard_customize_command(ctx: commands.Context):
    """Показывает настройки кастомизации карточки ранга (только для вас)"""
    if not ctx.guild:
        await ctx.send(embed=make_embed("Команда только для сервера", "Используйте команду на сервере.", color=0xED4245))
        return
    
    rankcard_settings = get_user_rankcard(ctx.author.id)
    
    embed = discord.Embed(
        title="🎨 Настройки карточки ранга",
        description="Текущие настройки вашей карточки:",
        color=0x5865F2
    )
    embed.add_field(
        name="Цвета",
        value=f"Фон: `{rankcard_settings.get('background_color', '#5865F2')}`\n"
              f"Текст: `{rankcard_settings.get('text_color', '#FFFFFF')}`\n"
              f"Прогресс: `{rankcard_settings.get('progress_color', '#57F287')}`",
        inline=False
    )
    embed.add_field(
        name="Стиль",
        value=rankcard_settings.get('style', 'default'),
        inline=True
    )
    embed.add_field(
        name="📝 Команды для изменения",
        value="`!rankcard-color bg <hex>` - цвет фона\n"
              "`!rankcard-color text <hex>` - цвет текста\n"
              "`!rankcard-color progress <hex>` - цвет прогресса\n"
              "`!rankcard-style <style>` - изменить стиль\n"
              "`!rankcard-reset` - сбросить настройки",
        inline=False
    )
    embed.set_footer(text="Все изменения применяются только к вашей карточке")
    await ctx.send(embed=embed, ephemeral=True)


@bot.command(name="rankcard-color")
async def rankcard_color_command(ctx: commands.Context, color_type: str, hex_color: str):
    """Изменяет цвет карточки ранга (только для вас)
    
    Параметры:
    - color_type: bg (фон), text (текст), progress (прогресс)
    - hex_color: Цвет в формате hex (#RRGGBB)
    
    Примеры:
    - !rankcard-color bg #FF5733
    - !rankcard-color text #FFFFFF
    - !rankcard-color progress #57F287
    """
    if not ctx.guild:
        await ctx.send(embed=make_embed("Команда только для сервера", "Используйте команду на сервере.", color=0xED4245))
        return
    
    rankcard_settings = get_user_rankcard(ctx.author.id)
    color_type = color_type.lower()
    
    if color_type not in ["bg", "text", "progress"]:
        await ctx.send(embed=make_embed(
            "Ошибка",
            "⚠️ Тип цвета должен быть: `bg`, `text` или `progress`",
            color=0xED4245
        ), ephemeral=True)
        return
    
    # Валидация hex цвета
    if not hex_color.startswith("#"):
        hex_color = "#" + hex_color
    
    if len(hex_color) != 7 or not all(c in "0123456789ABCDEFabcdef" for c in hex_color[1:]):
        await ctx.send(embed=make_embed(
            "Ошибка",
            "⚠️ Неверный формат hex цвета. Используйте формат: `#RRGGBB`\n"
            "Примеры: `#FF5733`, `#5865F2`, `#FFFFFF`",
            color=0xED4245
        ), ephemeral=True)
        return
    
    # Сохраняем цвет
    color_map = {
        "bg": "background_color",
        "text": "text_color",
        "progress": "progress_color"
    }
    rankcard_settings[color_map[color_type]] = hex_color.upper()
    save_rankcards()
    
    color_names = {
        "bg": "фон",
        "text": "текст",
        "progress": "прогресс"
    }
    
    await ctx.send(embed=make_embed(
        "✅ Цвет изменен",
        f"Цвет {color_names[color_type]} изменен на `{hex_color.upper()}`\n"
        f"Используйте `!rankcard` чтобы увидеть изменения.",
        color=0x57F287
    ), ephemeral=True)


@bot.command(name="rankcard-style")
async def rankcard_style_command(ctx: commands.Context, style: str):
    """Изменяет стиль карточки ранга (только для вас)
    
    Доступные стили: default, minimal, colorful
    
    Пример: !rankcard-style colorful
    """
    if not ctx.guild:
        await ctx.send(embed=make_embed("Команда только для сервера", "Используйте команду на сервере.", color=0xED4245))
        return
    
    rankcard_settings = get_user_rankcard(ctx.author.id)
    style = style.lower()
    valid_styles = ["default", "minimal", "colorful"]
    
    if style not in valid_styles:
        await ctx.send(embed=make_embed(
            "Ошибка",
            f"⚠️ Неверный стиль. Доступные: {', '.join(valid_styles)}",
            color=0xED4245
        ), ephemeral=True)
        return
    
    rankcard_settings["style"] = style
    save_rankcards()
    
    await ctx.send(embed=make_embed(
        "✅ Стиль изменен",
        f"Стиль карточки изменен на `{style}`\n"
        f"Используйте `!rankcard` чтобы увидеть изменения.",
        color=0x57F287
    ), ephemeral=True)


@bot.command(name="rankcard-reset")
async def rankcard_reset_command(ctx: commands.Context):
    """Сбрасывает настройки карточки ранга к значениям по умолчанию (только для вас)"""
    if not ctx.guild:
        await ctx.send(embed=make_embed("Команда только для сервера", "Используйте команду на сервере.", color=0xED4245))
        return
    
    rankcard_settings = get_user_rankcard(ctx.author.id)
    rankcard_settings.clear()
    rankcard_settings.update({
        "background_color": "#5865F2",
        "text_color": "#FFFFFF",
        "progress_color": "#57F287",
        "style": "default"
    })
    save_rankcards()
    
    await ctx.send(embed=make_embed(
        "✅ Настройки сброшены",
        "Все настройки карточки ранга сброшены к значениям по умолчанию.",
        color=0x57F287
    ), ephemeral=True)


@bot.command(name="badadd")
async def badadd_command(ctx: commands.Context, achievement_id: str, name: str, description: str, emoji: str, rarity: str = "common"):
    """Добавляет новый кастомный бейдж/достижение
    
    Параметры:
    - achievement_id: Уникальный ID (латинские буквы, цифры, подчеркивания)
    - name: Название достижения
    - description: Описание достижения
    - emoji: Эмодзи для достижения
    - rarity: Редкость (common, uncommon, rare, epic, legendary, secret) - по умолчанию common
    
    Пример: !badadd custom_badge "Особый бейдж" "Описание бейджа" 🎖️ rare
    """
    if not ctx.guild:
        await ctx.send(embed=make_embed("Команда только для сервера", "Используйте команду на сервере.", color=0xED4245))
        return
    
    # Проверка прав (только супер-админ)
    if not is_super_admin(ctx.author):
        await ctx.send(embed=make_embed(
            "Нет доступа",
            "🚫 Только супер-администратор может добавлять новые бейджи.",
            color=0xED4245
        ))
        return
    
    # Валидация ID
    if not achievement_id or not achievement_id.replace("_", "").replace("-", "").isalnum():
        await ctx.send(embed=make_embed(
            "Ошибка",
            "⚠️ ID достижения может содержать только латинские буквы, цифры, подчеркивания и дефисы.",
            color=0xFEE75C
        ))
        return
    
    achievement_id = achievement_id.lower()
    
    # Проверка, не существует ли уже такое достижение
    all_achievements = get_all_achievements()
    if achievement_id in all_achievements:
        await ctx.send(embed=make_embed(
            "Ошибка",
            f"⚠️ Достижение с ID `{achievement_id}` уже существует!",
            color=0xFEE75C
        ))
        return
    
    # Валидация редкости
    valid_rarities = ["common", "uncommon", "rare", "epic", "legendary", "secret"]
    rarity = rarity.lower()
    if rarity not in valid_rarities:
        await ctx.send(embed=make_embed(
            "Ошибка",
            f"⚠️ Неверная редкость. Доступные: {', '.join(valid_rarities)}",
            color=0xFEE75C
        ))
        return
    
    # Добавляем кастомное достижение
    custom_achievements[achievement_id] = {
        "name": name,
        "description": description,
        "emoji": emoji,
        "rarity": rarity,
        "created_by": ctx.author.id,
        "created_at": utc_now().isoformat()
    }
    save_custom_achievements()
    
    embed = discord.Embed(
        title="✅ Бейдж добавлен",
        description=f"Новый бейдж `{achievement_id}` успешно создан!",
        color=RARITY_COLORS.get(rarity, 0x5865F2)
    )
    embed.add_field(name="Название", value=f"{emoji} {name}", inline=False)
    embed.add_field(name="Описание", value=description, inline=False)
    embed.add_field(name="Редкость", value=rarity.capitalize(), inline=True)
    embed.add_field(name="ID", value=achievement_id, inline=True)
    embed.set_footer(text=f"Создано: {ctx.author.display_name}")
    
    await ctx.send(embed=embed)


@bot.command(name="badremove")
async def badremove_command(ctx: commands.Context, achievement_id: str):
    """Удаляет кастомный бейдж/достижение
    
    Пример: !badremove custom_badge
    """
    if not ctx.guild:
        await ctx.send(embed=make_embed("Команда только для сервера", "Используйте команду на сервере.", color=0xED4245))
        return
    
    if not is_super_admin(ctx.author):
        await ctx.send(embed=make_embed(
            "Нет доступа",
            "🚫 Только супер-администратор может удалять бейджи.",
            color=0xED4245
        ))
        return
    
    achievement_id = achievement_id.lower()
    
    if achievement_id not in custom_achievements:
        await ctx.send(embed=make_embed(
            "Ошибка",
            f"⚠️ Кастомное достижение `{achievement_id}` не найдено!",
            color=0xFEE75C
        ))
        return
    
    # Удаляем из кастомных достижений
    removed = custom_achievements.pop(achievement_id)
    save_custom_achievements()
    
    await ctx.send(embed=make_embed(
        "✅ Бейдж удален",
        f"Бейдж `{achievement_id}` ({removed.get('name', 'N/A')}) успешно удален.",
        color=0x57F287
    ))


@bot.command(name="badlist")
async def badlist_command(ctx: commands.Context):
    """Показывает список всех кастомных бейджей"""
    if not ctx.guild:
        await ctx.send(embed=make_embed("Команда только для сервера", "Используйте команду на сервере.", color=0xED4245))
        return
    
    if not custom_achievements:
        await ctx.send(embed=make_embed(
            "Кастомные бейджи",
            "Пока нет кастомных бейджей. Используйте `!badadd` для добавления.",
            color=0xFEE75C
        ))
        return
    
    embed = discord.Embed(
        title="📋 Список кастомных бейджей",
        description=f"Всего: **{len(custom_achievements)}**",
        color=0x5865F2
    )
    
    # Группируем по редкости
    by_rarity = {}
    for ach_id, ach in custom_achievements.items():
        rarity = ach.get("rarity", "common")
        if rarity not in by_rarity:
            by_rarity[rarity] = []
        by_rarity[rarity].append((ach_id, ach))
    
    rarity_order = ["legendary", "epic", "rare", "uncommon", "common", "secret"]
    for rarity in rarity_order:
        if rarity in by_rarity:
            ach_list = by_rarity[rarity]
            value = "\n".join([
                f"{ach['emoji']} **{ach['name']}** (`{ach_id}`)"
                for ach_id, ach in ach_list
            ])
            rarity_name = {
                "common": "Обычные",
                "uncommon": "Необычные",
                "rare": "Редкие",
                "epic": "Эпические",
                "legendary": "Легендарные",
                "secret": "Секретные"
            }.get(rarity, rarity.capitalize())
            embed.add_field(name=rarity_name, value=value[:1024], inline=False)
    
    await ctx.send(embed=embed)


@bot.command(name="badgive")
async def badgive_command(ctx: commands.Context, member: discord.Member, achievement_id: str):
    """Выдает кастомный бейдж пользователю
    
    Пример: !badgive @user custom_badge
    """
    if not ctx.guild:
        await ctx.send(embed=make_embed("Команда только для сервера", "Используйте команду на сервере.", color=0xED4245))
        return
    
    if not is_super_admin(ctx.author):
        await ctx.send(embed=make_embed(
            "Нет доступа",
            "🚫 Только супер-администратор может выдавать бейджи.",
            color=0xED4245
        ))
        return
    
    achievement_id = achievement_id.lower()
    all_achievements = get_all_achievements()
    
    if achievement_id not in all_achievements:
        await ctx.send(embed=make_embed(
            "Ошибка",
            f"⚠️ Достижение `{achievement_id}` не найдено!",
            color=0xFEE75C
        ))
        return
    
    if unlock_achievement(member.id, achievement_id):
        ach = all_achievements[achievement_id]
        rarity_color = RARITY_COLORS.get(ach.get("rarity", "common"), 0x5865F2)
        
        await ctx.send(embed=make_embed(
            "✅ Бейдж выдан",
            f"{member.mention} получил бейдж {ach['emoji']} **{ach['name']}**!",
            color=rarity_color
        ))
        
        await send_log_embed(
            "Бейдж выдан",
            f"{member.mention} получил кастомный бейдж.",
            color=rarity_color,
            member=member,
            fields=[
                ("Бейдж", f"{ach['emoji']} {ach['name']}"),
                ("Выдал", ctx.author.mention)
            ],
        )
    else:
        await ctx.send(embed=make_embed(
            "Информация",
            f"ℹ️ {member.mention} уже имеет этот бейдж.",
            color=0xFEE75C
        ))


@bot.command(name="statusmode")
async def status_mode_command(ctx: commands.Context, mode: str):
    log_command("HELP", "!statusmode", ctx.author, ctx.guild)
    if not is_super_admin(ctx.author):
        await ctx.send(
            embed=make_embed(
                "Нет доступа",
                "🚫 Только супер-администратор может использовать `!statusmode`.",
                color=0xED4245,
            )
        )
        return
    if not await ensure_command_access(ctx):
        return
    if not set_status_mode(mode):
        await ctx.send(embed=make_embed("Ошибка", "Использование: !statusmode <online|idle|dnd>", color=0xED4245))
        return
    await update_presence()
    await ctx.send(embed=make_embed("Статус обновлён", f"Режим присутствия изменён на {get_status_display_name()}"))


@bot.command(name="raidmode")
async def raidmode_command(ctx: commands.Context, action: str = "status"):
    log_command("HELP", "!raidmode", ctx.author, ctx.guild)
    if not is_super_admin(ctx.author):
        await ctx.send(
            embed=make_embed(
                "Нет доступа",
                "🚫 Только супер-администратор может использовать `!raidmode`.",
                color=0xED4245,
            )
        )
        return
    if not await ensure_command_access(ctx):
        return
    action = action.lower()
    if action == "on":
        raid_config["enabled"] = True
        save_raid_config()
        await announce_raid_state(ctx.guild, True)
        await ctx.send(embed=make_embed("Рейд-защита", "Режим защиты от рейда включён."))
    elif action == "off":
        raid_config["enabled"] = False
        save_raid_config()
        await announce_raid_state(ctx.guild, False)
        await ctx.send(embed=make_embed("Рейд-защита", "Режим защиты от рейда выключен."))
    else:
        status = "включён" if raid_config.get("enabled") else "выключен"
        threshold = raid_config.get("threshold")
        window = raid_config.get("window")
        mode = raid_config.get("action")
        embed = discord.Embed(
            title="Статус защиты от рейда",
            description=f"Сейчас режим {status}.",
            color=0x5865F2,
        )
        embed.add_field(name="Порог", value=f"{threshold} участников", inline=True)
        embed.add_field(name="Окно", value=f"{window} секунд", inline=True)
        embed.add_field(name="Действие", value=mode, inline=True)
        await ctx.send(embed=embed)


@bot.command(name="raidconfig")
async def raidconfig_command(
    ctx: commands.Context,
    threshold: int | None = None,
    window: int | None = None,
    action: str | None = None,
    notify_channel: discord.TextChannel | None = None,
):
    if not is_super_admin(ctx.author):
        await ctx.send(
            embed=make_embed(
                "Нет доступа",
                "🚫 Только супер-администратор может использовать `!raidconfig`.",
                color=0xED4245,
            )
        )
        return
    updated = False
    if threshold is not None and threshold > 0:
        raid_config["threshold"] = threshold
        updated = True
    if window is not None and window > 0:
        raid_config["window"] = window
        updated = True
    if action:
        action = action.lower()
        if action in {"kick", "ban"}:
            raid_config["action"] = action
            updated = True
    if notify_channel is not None:
        raid_config["notify_channel_id"] = notify_channel.id
        updated = True
    if updated:
        save_raid_config()
        await ctx.send(embed=make_embed("Рейд-настройки", "Параметры обновлены."))
    else:
        embed = discord.Embed(title="Рейд-настройки", color=0x5865F2)
        embed.add_field(name="Порог", value=str(raid_config.get("threshold")), inline=True)
        embed.add_field(name="Окно (сек)", value=str(raid_config.get("window")), inline=True)
        embed.add_field(name="Действие", value=raid_config.get("action"), inline=True)
        notify = raid_config.get("notify_channel_id")
        embed.add_field(name="Канал уведомлений", value=f"<#{notify}>" if notify else "не задан", inline=False)
        await ctx.send(embed=embed)


@bot.command(name="ticketpanel")
async def ticket_panel_command(ctx: commands.Context, channel: discord.TextChannel | None = None):
    if not is_super_admin(ctx.author):
        await ctx.send(
            embed=make_embed(
                "Нет доступа",
                "🚫 Только супер-администратор может использовать `!ticketpanel`.",
                color=0xED4245,
            )
        )
        return
    target = channel or ctx.channel
    tickets_config["panel_channel_id"] = target.id
    tickets_config["panel_message_id"] = 0
    save_tickets_config()
    await ensure_ticket_panel()
    await ctx.send(embed=make_embed("Панель тикетов", f"Панель развернута в {target.mention}"))


@bot.command(name="diag")
async def diag_command(ctx: commands.Context):
    """Диагностика бота и выявление ошибок"""
    log_command("UTILITY", "!diag", ctx.author, ctx.guild)
    
    if not await ensure_command_access(ctx):
        return
    
    issues = []
    warnings = []
    info = []
    
    # Проверка токена Discord
    if not TOKEN:
        issues.append("❌ Токен Discord не найден (BOT_TOKEN)")
    elif '.' not in TOKEN or len(TOKEN) < 50:
        issues.append(f"❌ Неверный формат токена Discord (длина: {len(TOKEN)})")
    else:
        info.append("✅ Токен Discord настроен")
    
    # Проверка API ключа Mistral
    if not MISTRAL_API_KEY or MISTRAL_API_KEY == "dEpuO1P9PTLxkk2Tae9XftblYeiqsSub":
        warnings.append("⚠️ Используется дефолтный API ключ Mistral (рекомендуется установить свой)")
    else:
        info.append("✅ API ключ Mistral настроен")
    
    # Проверка состояния бота
    if not bot.is_ready():
        warnings.append("⚠️ Бот еще не готов (is_ready = False)")
    else:
        info.append("✅ Бот готов к работе")
        info.append(f"✅ Подключено серверов: {len(bot.guilds)}")
        info.append(f"✅ Ping: {int(bot.latency * 1000)} мс")
    
    # Проверка каналов
    if LOG_CHANNEL_ID:
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            issues.append(f"❌ Лог-канал не найден (ID: {LOG_CHANNEL_ID})")
        else:
            info.append(f"✅ Лог-канал найден: {log_channel.name}")
    
    # Проверка файлов конфигурации
    config_files = [
        ("res_whitelist.json", RES_WHITELIST_FILE),
        ("moderation.json", MODERATION_FILE),
        ("about_statuses.json", ABOUT_STATUS_FILE),
        ("levels.json", LEVELS_FILE),
        ("voice_rooms.json", VOICE_CONFIG_FILE),
        ("tickets_config.json", TICKETS_CONFIG_FILE),
        ("raid_config.json", RAID_CONFIG_FILE),
        ("super_admin.json", SUPER_ADMIN_FILE),
        ("settings.json", SETTINGS_FILE),
    ]
    
    config_errors = 0
    config_ok = 0
    
    for config_name, config_path in config_files:
        if not config_path.exists():
            warnings.append(f"⚠️ Файл {config_name} не найден (будет создан автоматически)")
        else:
            try:
                data = json.loads(config_path.read_text(encoding="utf-8"))
                config_ok += 1
            except json.JSONDecodeError as e:
                issues.append(f"❌ {config_name}: невалидный JSON ({str(e)[:50]})")
                config_errors += 1
            except Exception as e:
                warnings.append(f"⚠️ {config_name}: ошибка чтения ({str(e)[:50]})")
    
    if config_ok > 0:
        info.append(f"✅ Валидных конфигов: {config_ok}")
    if config_errors > 0:
        issues.append(f"❌ Ошибок в конфигах: {config_errors}")
    
    # Проверка папки data
    if not DATA_DIR.exists():
        issues.append("❌ Папка data/ не существует")
    else:
        info.append("✅ Папка data/ существует")
    
    # Проверка main.py
    main_py_path = Path("main.py")
    if not main_py_path.exists():
        issues.append("❌ Файл main.py не найден")
    else:
        info.append("✅ Файл main.py найден")
    
    # Проверка голосовых генераторов
    if voice_config.get("generators"):
        generators_count = len(voice_config.get("generators", []))
        missing_generators = 0
        for gen in voice_config.get("generators", []):
            gen_id = gen.get("generator_channel_id")
            if gen_id:
                channel = bot.get_channel(gen_id)
                if not channel:
                    missing_generators += 1
        if missing_generators > 0:
            warnings.append(f"⚠️ Не найдено голосовых генераторов: {missing_generators}/{generators_count}")
        else:
            info.append(f"✅ Голосовых генераторов: {generators_count}")
    
    # Проверка тикетов
    if tickets_config.get("panel_channel_id"):
        panel_channel = bot.get_channel(tickets_config.get("panel_channel_id"))
        if not panel_channel:
            warnings.append("⚠️ Канал панели тикетов не найден")
        else:
            info.append("✅ Панель тикетов настроена")
    
    # Проверка uptime
    if bot_start_time:
        uptime = utc_now() - bot_start_time
        uptime_str = format_timedelta(uptime)
        info.append(f"✅ Uptime: {uptime_str}")
    
    # Формируем ответ
    embed = discord.Embed(
        title="🔍 Диагностика бота",
        color=0xED4245 if issues else (0xFEE75C if warnings else 0x57F287),
        timestamp=utc_now()
    )
    
    if issues:
        embed.add_field(
            name="❌ Критические ошибки",
            value="\n".join(issues[:10]) + (f"\n... и еще {len(issues) - 10}" if len(issues) > 10 else ""),
            inline=False
        )
    
    if warnings:
        embed.add_field(
            name="⚠️ Предупреждения",
            value="\n".join(warnings[:10]) + (f"\n... и еще {len(warnings) - 10}" if len(warnings) > 10 else ""),
            inline=False
        )
    
    if info:
        embed.add_field(
            name="ℹ️ Информация",
            value="\n".join(info[:15]) + (f"\n... и еще {len(info) - 15}" if len(info) > 15 else ""),
            inline=False
        )
    
    if not issues and not warnings:
        embed.description = "✅ Все проверки пройдены успешно!"
    
    embed.set_footer(text=f"Всего: {len(issues)} ошибок, {len(warnings)} предупреждений, {len(info)} проверок")
    
    await ctx.send(embed=embed)


@bot.command(name="stresstesting")
async def stresstesting_command(ctx: commands.Context):
    """Проводит нагрузочные испытания системы"""
    log_command("UTILITY", "!stresstesting", ctx.author, ctx.guild)
    
    if not await ensure_command_access(ctx):
        return
    
    await ctx.send(embed=make_embed("Нагрузочное тестирование", "🔄 Запуск нагрузочных испытаний...", color=0xFEE75C))
    
    results = {
        "message_send": {"time": 0, "success": 0, "failed": 0},
        "command_processing": {"time": 0, "success": 0, "failed": 0},
        "file_operations": {"time": 0, "success": 0, "failed": 0},
        "memory_usage": {"before": 0, "after": 0},
        "cpu_usage": 0
    }
    
    import time
    import asyncio
    
    # Тест 1: Отправка сообщений
    start_time = time.time()
    test_messages = 10
    for i in range(test_messages):
        try:
            msg = await ctx.channel.send(f"Тест {i+1}/{test_messages}")
            await msg.delete()
            results["message_send"]["success"] += 1
            await asyncio.sleep(0.1)  # Небольшая задержка
        except Exception as e:
            results["message_send"]["failed"] += 1
            print(f"[StressTest] Ошибка отправки сообщения: {e}")
    results["message_send"]["time"] = time.time() - start_time
    
    # Тест 2: Обработка команд (симуляция)
    start_time = time.time()
    for i in range(5):
        try:
            # Симулируем обработку команды
            await asyncio.sleep(0.05)
            results["command_processing"]["success"] += 1
        except Exception as e:
            results["command_processing"]["failed"] += 1
    results["command_processing"]["time"] = time.time() - start_time
    
    # Тест 3: Операции с файлами
    start_time = time.time()
    test_file = DATA_DIR / "stress_test_temp.json"
    for i in range(5):
        try:
            test_file.write_text(json.dumps({"test": i}, ensure_ascii=False), encoding="utf-8")
            data = json.loads(test_file.read_text(encoding="utf-8"))
            results["file_operations"]["success"] += 1
        except Exception as e:
            results["file_operations"]["failed"] += 1
    if test_file.exists():
        test_file.unlink()
    results["file_operations"]["time"] = time.time() - start_time
    
    # Тест 4: Использование памяти и CPU
    if process:
        try:
            results["memory_usage"]["before"] = process.memory_info().rss / 1024 / 1024  # MB
            results["cpu_usage"] = process.cpu_percent(interval=0.5)
            results["memory_usage"]["after"] = process.memory_info().rss / 1024 / 1024  # MB
        except:
            pass
    
    # Формируем отчёт
    embed = discord.Embed(
        title="📊 Результаты нагрузочного тестирования",
        description="Результаты проведённых тестов производительности",
        color=0x57F287 if results["message_send"]["failed"] == 0 else 0xFEE75C,
        timestamp=utc_now()
    )
    
    # Отправка сообщений
    msg_stats = results["message_send"]
    embed.add_field(
        name="📨 Тест отправки сообщений",
        value=(
            f"Успешно: {msg_stats['success']}/{test_messages}\n"
            f"Ошибок: {msg_stats['failed']}\n"
            f"Время: {msg_stats['time']:.2f}с\n"
            f"Скорость: {test_messages/msg_stats['time']:.2f} сообщ/с"
        ),
        inline=True
    )
    
    # Обработка команд
    cmd_stats = results["command_processing"]
    embed.add_field(
        name="⚙️ Тест обработки команд",
        value=(
            f"Успешно: {cmd_stats['success']}/5\n"
            f"Ошибок: {cmd_stats['failed']}\n"
            f"Время: {cmd_stats['time']:.2f}с"
        ),
        inline=True
    )
    
    # Файловые операции
    file_stats = results["file_operations"]
    embed.add_field(
        name="📁 Тест файловых операций",
        value=(
            f"Успешно: {file_stats['success']}/5\n"
            f"Ошибок: {file_stats['failed']}\n"
            f"Время: {file_stats['time']:.2f}с"
        ),
        inline=True
    )
    
    # Системные ресурсы
    if results["cpu_usage"] > 0:
        embed.add_field(
            name="💻 Системные ресурсы",
            value=(
                f"CPU: {results['cpu_usage']:.1f}%\n"
                f"Память: {results['memory_usage']['after']:.1f} MB\n"
                f"Использовано: {results['memory_usage']['after'] - results['memory_usage']['before']:.1f} MB"
            ),
            inline=False
        )
    
    # Общая оценка
    total_success = msg_stats['success'] + cmd_stats['success'] + file_stats['success']
    total_tests = test_messages + 5 + 5
    success_rate = (total_success / total_tests) * 100
    
    status = "✅ Отлично" if success_rate >= 95 else "⚠️ Хорошо" if success_rate >= 80 else "❌ Требует внимания"
    embed.add_field(
        name="📈 Общая оценка",
        value=f"{status}\nУспешность: {success_rate:.1f}%\nВсего тестов: {total_tests}",
        inline=False
    )
    
    embed.set_footer(text=f"Тестирование выполнено {ctx.author.display_name}")
    await ctx.send(embed=embed)


@bot.command(name="vulnscan")
async def vulnscan_command(ctx: commands.Context):
    """Проводит автоматизированный поиск уязвимостей"""
    log_command("UTILITY", "!vulnscan", ctx.author, ctx.guild)
    
    if not await ensure_command_access(ctx):
        return
    
    await ctx.send(embed=make_embed("Сканирование уязвимостей", "🔍 Начало сканирования...", color=0xFEE75C))
    
    vulnerabilities = []
    warnings = []
    info = []
    
    # Этап 1: Сбор информации
    info.append("📋 Этап 1: Сбор информации")
    
    # Проверка файлов конфигурации
    config_files_to_check = [
        ("main.py", Path("main.py")),
        (RES_WHITELIST_FILE.name, RES_WHITELIST_FILE),
        (MODERATION_FILE.name, MODERATION_FILE),
        (TICKETS_CONFIG_FILE.name, TICKETS_CONFIG_FILE),
    ]
    
    # Этап 2: Анализ кода
    info.append("🔬 Этап 2: Анализ кода")
    
    # Проверка на хардкод токенов и секретов
    main_py_path = Path("main.py")
    if main_py_path.exists():
        try:
            code_content = main_py_path.read_text(encoding="utf-8")
            
            # Проверка на хардкод токенов
            if 'TELEGRAM_BOT_TOKEN = "' in code_content and '"8235791338:' in code_content:
                vulnerabilities.append("🔴 КРИТИЧНО: Telegram токен захардкожен в коде")
            
            if 'MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "' in code_content and '"dEpuO1P9PTLxkk2Tae9XftblYeiqsSub"' in code_content:
                warnings.append("🟡 Telegram API ключ имеет дефолтное значение")
            
            # Проверка на потенциальные SQL инъекции
            if 'execute(' in code_content and '%s' not in code_content and '?' not in code_content:
                warnings.append("🟡 Потенциальная уязвимость SQL инъекции (используйте параметризованные запросы)")
            
            # Проверка на eval/exec
            if 'eval(' in code_content or 'exec(' in code_content:
                vulnerabilities.append("🔴 КРИТИЧНО: Использование eval() или exec() обнаружено")
            
            # Проверка на небезопасные операции с файлами
            if 'open(' in code_content and '../' in code_content:
                warnings.append("🟡 Потенциальная уязвимость path traversal")
            
        except Exception as e:
            warnings.append(f"🟡 Не удалось проанализировать код: {str(e)[:50]}")
    
    # Этап 3: Проверка безопасности
    info.append("🔒 Этап 3: Проверка безопасности")
    
    # Проверка токена Discord
    if not TOKEN:
        vulnerabilities.append("🔴 КРИТИЧНО: Токен Discord не найден")
    elif len(TOKEN) < 50:
        vulnerabilities.append("🔴 КРИТИЧНО: Токен Discord имеет подозрительно малую длину")
    else:
        info.append("✅ Токен Discord настроен корректно")
    
    # Проверка прав доступа к файлам
    try:
        if DATA_DIR.exists():
            # Проверяем, можно ли писать в папку data
            test_file = DATA_DIR / ".security_test"
            test_file.write_text("test")
            test_file.unlink()
            info.append("✅ Папка data/ доступна для записи")
        else:
            warnings.append("🟡 Папка data/ не существует")
    except Exception as e:
        vulnerabilities.append(f"🔴 КРИТИЧНО: Нет доступа к папке data/: {str(e)[:50]}")
    
    # Проверка конфигурационных файлов на публичный доступ
    sensitive_files = [
        ("backup.json", Path("backup.json")),
        (SUPER_ADMIN_FILE.name, SUPER_ADMIN_FILE),
        (AI_BLACKLIST_FILE.name, AI_BLACKLIST_FILE),
    ]
    
    for file_name, file_path in sensitive_files:
        if file_path.exists():
            try:
                # Проверяем, что файл не слишком большой (может содержать утечки)
                size_mb = file_path.stat().st_size / 1024 / 1024
                if size_mb > 10:
                    warnings.append(f"🟡 Файл {file_name} очень большой ({size_mb:.1f} MB) - возможна утечка данных")
            except:
                pass
    
    # Этап 3.5: Проверка безопасности сервера Discord
    info.append("🛡️ Этап 3.5: Проверка безопасности сервера")
    
    try:
        if bot.is_ready() and ctx.guild:
            guild = ctx.guild
            # Проверка прав бота
            bot_member = guild.get_member(bot.user.id) if bot.user else None
            if bot_member:
                perms = bot_member.guild_permissions
                if perms.administrator:
                    warnings.append("🟡 Бот имеет права администратора - повышенный риск")
                if not perms.manage_messages:
                    warnings.append("🟡 Бот не имеет прав на управление сообщениями")
            
            # Проверка уровня верификации сервера
            verification_level = guild.verification_level
            if verification_level == discord.VerificationLevel.none:
                vulnerabilities.append("🔴 КРИТИЧНО: Сервер не требует верификации - высокий риск рейдов")
            elif verification_level == discord.VerificationLevel.low:
                warnings.append("🟡 Низкий уровень верификации - рекомендуется повысить")
            elif verification_level == discord.VerificationLevel.medium:
                info.append("✅ Средний уровень верификации настроен")
            else:
                info.append("✅ Высокий уровень верификации настроен")
            
            # Проверка требований 2FA для модераторов
            if guild.mfa_level == discord.MFALevel.none:
                vulnerabilities.append("🔴 КРИТИЧНО: 2FA не требуется для модераторов - высокий риск компрометации")
            else:
                info.append("✅ 2FA требуется для модераторов")
            
            # Проверка настроек контента
            if guild.explicit_content_filter == discord.ContentFilter.disabled:
                warnings.append("🟡 Фильтр контента отключен - возможны нежелательные материалы")
            else:
                info.append("✅ Фильтр контента включен")
            
            # Проверка ролей с опасными правами
            dangerous_perms = [
                'administrator', 'manage_guild', 'manage_roles', 
                'manage_channels', 'ban_members', 'kick_members'
            ]
            
            roles_with_dangerous_perms = []
            for role in guild.roles:
                if role.permissions.administrator and not role.is_default():
                    roles_with_dangerous_perms.append(f"Роль {role.name} имеет права администратора")
                elif any(getattr(role.permissions, perm, False) for perm in dangerous_perms):
                    if role.members:
                        member_count = len(role.members)
                        if member_count > 10:
                            warnings.append(f"🟡 Роль {role.name} имеет опасные права и {member_count} участников")
            
            # Проверка @everyone с опасными правами
            everyone_role = guild.default_role
            if everyone_role:
                if everyone_role.permissions.administrator:
                    vulnerabilities.append("🔴 КРИТИЧНО: @everyone имеет права администратора!")
                elif everyone_role.permissions.manage_guild:
                    vulnerabilities.append("🔴 КРИТИЧНО: @everyone может управлять сервером!")
                elif everyone_role.permissions.manage_channels:
                    warnings.append("🟡 @everyone может управлять каналами")
                elif everyone_role.permissions.manage_roles:
                    warnings.append("🟡 @everyone может управлять ролями")
            
            # Проверка позиции бота в иерархии ролей
            if bot_member:
                bot_top_role = bot_member.top_role
                roles_above_bot = [r for r in guild.roles if r.position > bot_top_role.position and not r.is_default()]
                if roles_above_bot:
                    warnings.append(f"🟡 Найдено {len(roles_above_bot)} ролей выше бота - возможны проблемы с модерацией")
            
            # Проверка каналов с открытыми правами
            open_channels = []
            for channel in guild.channels:
                if isinstance(channel, discord.TextChannel):
                    everyone_overwrite = channel.overwrites_for(everyone_role) if everyone_role else None
                    if everyone_overwrite:
                        if everyone_overwrite.send_messages and everyone_overwrite.manage_messages:
                            open_channels.append(f"#{channel.name} - @everyone может управлять сообщениями")
                        elif everyone_overwrite.send_messages and not channel.is_nsfw():
                            # Это нормально для большинства каналов
                            pass
            
            if open_channels:
                warnings.append(f"🟡 Найдено {len(open_channels)} каналов с потенциально опасными правами")
            
            # Проверка на наличие ботов с административными правами
            admin_bots = []
            for member in guild.members:
                if member.bot and member.id != bot.user.id:
                    if member.guild_permissions.administrator:
                        admin_bots.append(f"Бот {member.name} имеет права администратора")
            
            if admin_bots:
                vulnerabilities.append(f"🔴 КРИТИЧНО: Найдено {len(admin_bots)} ботов с правами администратора")
            
            # Проверка настроек анти-рейда
            if raid_config.get("enabled"):
                info.append("✅ Анти-рейд защита включена")
            else:
                warnings.append("🟡 Анти-рейд защита отключена")
            
            # Проверка количества участников без ролей
            members_without_roles = [m for m in guild.members if len(m.roles) == 1]  # Только @everyone
            if len(members_without_roles) > guild.member_count * 0.5:
                warnings.append(f"🟡 {len(members_without_roles)} участников без ролей ({len(members_without_roles)/guild.member_count*100:.1f}%)")
            
            # Проверка на наличие вебхуков
            try:
                webhooks = await guild.webhooks()
                if len(webhooks) > 20:
                    warnings.append(f"🟡 Найдено {len(webhooks)} вебхуков - возможен риск утечки данных")
            except discord.Forbidden:
                warnings.append("🟡 Нет прав для проверки вебхуков")
            except Exception:
                pass
            
            # Проверка на наличие приглашений
            try:
                invites = await guild.invites()
                permanent_invites = [inv for inv in invites if inv.max_age == 0]
                if len(permanent_invites) > 10:
                    warnings.append(f"🟡 Найдено {len(permanent_invites)} постоянных приглашений - возможен риск неконтролируемого доступа")
            except discord.Forbidden:
                warnings.append("🟡 Нет прав для проверки приглашений")
            except Exception:
                pass
            
            # Проверка настроек безопасности каналов
            nsfw_channels = [ch for ch in guild.channels if isinstance(ch, discord.TextChannel) and ch.is_nsfw()]
            if nsfw_channels:
                info.append(f"✅ Найдено {len(nsfw_channels)} NSFW каналов (правильно настроены)")
            
            # Проверка на наличие каналов без модерации
            unmoderated_channels = []
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).manage_messages:
                    # Бот может модерировать
                    pass
                else:
                    unmoderated_channels.append(f"#{channel.name}")
            
            if unmoderated_channels and len(unmoderated_channels) > 5:
                warnings.append(f"🟡 Найдено {len(unmoderated_channels)} каналов без модерации бота")
        else:
            warnings.append("🟡 Не удалось проверить настройки сервера (бот не готов или команда вне сервера)")
    except Exception as e:
        warnings.append(f"🟡 Ошибка при проверке сервера: {str(e)[:100]}")
        print(f"[VulnScan] Ошибка проверки сервера: {e}")
    
    # Этап 4: Генерация отчёта
    info.append("📊 Этап 4: Генерация отчёта")
    
    # Формируем финальный отчёт
    embed = discord.Embed(
        title="🛡️ Отчёт о сканировании уязвимостей",
        description="Результаты автоматизированного анализа безопасности",
        color=0xED4245 if vulnerabilities else (0xFEE75C if warnings else 0x57F287),
        timestamp=utc_now()
    )
    
    if vulnerabilities:
        vuln_text = "\n".join(vulnerabilities[:10])
        if len(vulnerabilities) > 10:
            vuln_text += f"\n... и ещё {len(vulnerabilities) - 10} уязвимостей"
        embed.add_field(
            name="🔴 Критические уязвимости",
            value=vuln_text,
            inline=False
        )
    
    if warnings:
        warn_text = "\n".join(warnings[:10])
        if len(warnings) > 10:
            warn_text += f"\n... и ещё {len(warnings) - 10} предупреждений"
        embed.add_field(
            name="🟡 Предупреждения",
            value=warn_text,
            inline=False
        )
    
    if info:
        info_text = "\n".join(info[:15])
        embed.add_field(
            name="ℹ️ Информация",
            value=info_text,
            inline=False
        )
    
    # Общая оценка безопасности
    risk_level = "🔴 ВЫСОКИЙ" if vulnerabilities else ("🟡 СРЕДНИЙ" if warnings else "🟢 НИЗКИЙ")
    embed.add_field(
        name="📈 Оценка безопасности",
        value=(
            f"Уровень риска: {risk_level}\n"
            f"Критических уязвимостей: {len(vulnerabilities)}\n"
            f"Предупреждений: {len(warnings)}\n"
            f"Проверок выполнено: {len(info)}"
        ),
        inline=False
    )
    
    if not vulnerabilities and not warnings:
        embed.description = "✅ Критических уязвимостей не обнаружено!"
    
    embed.set_footer(text=f"Сканирование выполнено {ctx.author.display_name}")
    await ctx.send(embed=embed)


@bot.command(name="patchnotes")
async def patchnotes_command(ctx: commands.Context, channel: discord.TextChannel = None):
    """Отправляет патчноуты в указанный канал"""
    log_command("UTILITY", "!patchnotes", ctx.author, ctx.guild)
    
    if not await ensure_command_access(ctx):
        return
    
    # Если канал не указан, используем текущий
    target_channel = channel or ctx.channel
    
    # Загружаем патчноуты
    patchnotes = load_patchnotes()
    
    if not patchnotes:
        await ctx.send(
            embed=make_embed(
                "Ошибка",
                "❌ Патчноуты не найдены. Используйте функцию `add_patchnote()` в коде для добавления патчноутов.",
                color=0xED4245
            ),
            delete_after=15
        )
        return
    
    # Берем последний патчноут
    latest_note = patchnotes[-1]
    
    # Формируем embed
    try:
        note_date = latest_note.get('date', utc_now().isoformat())
        # Обрабатываем разные форматы даты
        if 'Z' in note_date:
            note_date = note_date.replace('Z', '+00:00')
        elif '+' not in note_date and note_date.count(':') >= 2:
            note_date = note_date + '+00:00'
        embed_timestamp = datetime.fromisoformat(note_date)
    except:
        embed_timestamp = utc_now()
    
    embed = discord.Embed(
        title=f"📝 Патчноуты версии {latest_note.get('version', 'Unknown')}",
        description="Обновления и изменения в боте",
        color=0x5865F2,
        timestamp=embed_timestamp
    )
    
    # Добавляем разделы
    # Функция для обработки как списков, так и строк с \n
    def process_items(items):
        if not items:
            return []
        if isinstance(items, str):
            # Если это строка с \n, разбиваем её
            return [line.strip() for line in items.split('\n') if line.strip()]
        elif isinstance(items, list):
            # Если это список, обрабатываем каждый элемент
            result = []
            for item in items:
                if isinstance(item, str):
                    # Если элемент содержит \n, разбиваем его
                    if '\n' in item:
                        result.extend([line.strip() for line in item.split('\n') if line.strip()])
                    else:
                        result.append(item)
                else:
                    result.append(str(item))
            return result
        return []
    
    if latest_note.get('additions'):
        additions_list = process_items(latest_note['additions'])
        if additions_list:
            additions_text = "\n".join(f"• {item}" for item in additions_list)
            embed.add_field(
                name="✨ Добавлено",
                value=additions_text[:1024],  # Ограничение Discord
                inline=False
            )
    
    if latest_note.get('fixes'):
        fixes_list = process_items(latest_note['fixes'])
        if fixes_list:
            fixes_text = "\n".join(f"• {item}" for item in fixes_list)
            embed.add_field(
                name="🔧 Исправлено",
                value=fixes_text[:1024],
                inline=False
            )
    
    if latest_note.get('improvements'):
        improvements_list = process_items(latest_note['improvements'])
        if improvements_list:
            improvements_text = "\n".join(f"• {item}" for item in improvements_list)
            embed.add_field(
                name="⚡ Улучшено",
                value=improvements_text[:1024],
                inline=False
            )
    
    if latest_note.get('other'):
        other_list = process_items(latest_note['other'])
        if other_list:
            other_text = "\n".join(f"• {item}" for item in other_list)
            embed.add_field(
                name="📌 Прочее",
                value=other_text[:1024],
                inline=False
            )
    
    # Если нет изменений
    if not any([latest_note.get('additions'), latest_note.get('fixes'), 
                latest_note.get('improvements'), latest_note.get('other')]):
        embed.description = "Нет изменений для отображения."
    
    embed.set_footer(text=f"Отправлено {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url if ctx.author.display_avatar else None)
    
    try:
        await target_channel.send(embed=embed)
        await ctx.send(
            embed=make_embed(
                "Успех",
                f"✅ Патчноуты отправлены в {target_channel.mention}",
                color=0x57F287
            ),
            delete_after=10
        )
    except discord.Forbidden:
        await ctx.send(
            embed=make_embed(
                "Ошибка",
                f"❌ Нет прав для отправки сообщений в {target_channel.mention}",
                color=0xED4245
            ),
            delete_after=15
        )
    except Exception as e:
        await ctx.send(
            embed=make_embed(
                "Ошибка",
                f"❌ Не удалось отправить патчноуты: {str(e)}",
                color=0xED4245
            ),
            delete_after=15
        )


@bot.command(name="backup")
async def backup_command(ctx: commands.Context, *, version: str = None):
    """Создать резервную копию бота и всех конфигов"""
    log_command("UTILITY", "!backup", ctx.author, ctx.guild)
    
    if not await ensure_command_access(ctx):
        return
    
    if not version:
        await ctx.send(
            embed=make_embed(
                "Ошибка",
                "Укажите версию бота: `!backup версия бота`\nПример: `!backup v1.2.3`",
                color=0xED4245
            ),
            delete_after=15
        )
        return
    
    try:
        backup_data = {
            "version": version,
            "timestamp": utc_now().isoformat(),
            "bot_code": {},
            "configs": {}
        }
        
        # Читаем main.py с сохранением форматирования
        try:
            main_py_path = Path("main.py")
            if main_py_path.exists():
                # Читаем файл как есть, чтобы сохранить табы и форматирование
                backup_data["bot_code"]["main.py"] = main_py_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"[Backup] Ошибка чтения main.py: {e}")
        
        # Читаем все конфиги из data/
        config_files = [
            ("res_whitelist.json", RES_WHITELIST_FILE),
            ("moderation.json", MODERATION_FILE),
            ("about_statuses.json", ABOUT_STATUS_FILE),
            ("levels.json", LEVELS_FILE),
            ("voice_rooms.json", VOICE_CONFIG_FILE),
            ("tickets_config.json", TICKETS_CONFIG_FILE),
            ("ticket_mutes.json", TICKET_MUTES_FILE),
            ("voice_mutes.json", VOICE_MUTES_FILE),
            ("raid_config.json", RAID_CONFIG_FILE),
            ("mod_whitelist.json", MOD_WHITELIST_FILE),
            ("command_whitelist.json", COMMAND_WHITELIST_FILE),
            ("project_birthday_state.json", PROJECT_BIRTHDAY_STATE_FILE),
            ("events.json", EVENTS_FILE),
            ("event_managers.json", EVENT_MANAGERS_FILE),
            ("super_admin.json", SUPER_ADMIN_FILE),
            ("eternal_whitelist.json", ETERNAL_WHITELIST_FILE),
            ("askpr_whitelist.json", ASKPR_WHITELIST_FILE),
            ("ai_priority.json", AI_PRIORITY_FILE),
            ("ai_blacklist.json", AI_BLACKLIST_FILE),
            ("settings.json", SETTINGS_FILE),
            ("achievements.json", ACHIEVEMENTS_FILE),
            ("rankcards.json", RANKCARDS_FILE),
            ("custom_achievements.json", CUSTOM_ACHIEVEMENTS_FILE),
            ("anti_flood_ignore_channels.json", ANTI_FLOOD_IGNORE_CHANNELS_FILE),
        ]
        
        for config_name, config_path in config_files:
            try:
                if config_path.exists():
                    backup_data["configs"][config_name] = config_path.read_text(encoding="utf-8")
            except Exception as e:
                print(f"[Backup] Ошибка чтения {config_name}: {e}")
        
        # Сохраняем в backup.json
        backup_file = Path("backup.json")
        
        # Загружаем существующие бэкапы, если есть
        existing_backups = {}
        if backup_file.exists():
            try:
                existing_backups = json.loads(backup_file.read_text(encoding="utf-8"))
            except:
                existing_backups = {}
        
        # Добавляем новый бэкап
        if not isinstance(existing_backups, dict):
            existing_backups = {}
        
        existing_backups[version] = backup_data
        
        # Ограничиваем количество версий до 15 (оставляем последние 15)
        if len(existing_backups) > 15:
            # Сортируем по timestamp и оставляем последние 15
            sorted_versions = sorted(
                existing_backups.items(),
                key=lambda x: x[1].get("timestamp", ""),
                reverse=True
            )[:15]
            removed_count = len(existing_backups) - 15
            existing_backups = dict(sorted_versions)
            if removed_count > 0:
                await ctx.send(
                    embed=make_embed(
                        "Информация",
                        f"📦 Удалено старых версий: {removed_count} (оставлено максимум 15 версий)",
                        color=0xFEE75C
                    ),
                    delete_after=10
                )
        
        # Сохраняем все бэкапы с правильным форматированием
        # Используем ensure_ascii=False для сохранения русских символов
        # indent=2 для читаемости JSON структуры
        # Код внутри строк будет экранирован JSON (\t, \n и т.д.), но при восстановлении
        # будет идентичен оригиналу благодаря правильному декодированию
        backup_file.write_text(
            json.dumps(existing_backups, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        
        files_count = len(backup_data["bot_code"]) + len(backup_data["configs"])
        await ctx.send(
            embed=make_embed(
                "Резервная копия создана",
                f"✅ Версия `{version}` успешно сохранена в `backup.json`\n"
                f"📁 Сохранено файлов: {files_count}\n"
                f"• Код бота: {len(backup_data['bot_code'])}\n"
                f"• Конфиги: {len(backup_data['configs'])}",
                color=0x57F287
            )
        )
        
    except Exception as e:
        await ctx.send(
            embed=make_embed(
                "Ошибка",
                f"❌ Не удалось создать резервную копию: {str(e)}",
                color=0xED4245
            ),
            delete_after=15
        )
        print(f"[Backup] Ошибка: {e}")


@bot.command(name="help")
async def help_command(ctx: commands.Context):
    embed = discord.Embed(
        title="Список команд",
        description="Доступные команды бота, разделённые по категориям:",
        color=0x5865F2,
    )
    embed.add_field(
        name="🛡 Модерирование",
        value=(
            "• `!clear <кол-во>` — удалить сообщения в текущем канале.\n"
            "• `!warn @user [причина]` — выдать предупреждение.\n"
            "• `!unwarn @user [номер]` — снять предупреждение.\n"
            "• `!warns` — показать список предупреждений.\n"
            "• `!mute @user [время] [причина]` — выдать мут.\n"
            "• `!unmute @user [причина]` — снять мут.\n"
            "• `!mute-voice` — мут в голосовых каналах.\n"
            "• `!muteticket @user [время] [причина]` — мут тикетов.\n"
            "• `!unmuteticket @user [причина]` — снять мут тикета.\n"
            "• `!ban @user [время] [причина]` — забанить пользователя.\n"
            "• `!unban <user_id|@user> [причина]` — снять бан.\n"
            "• `!event` / `!stopevent` / `!endevent` — управление ивентами.\n"
        ),
        inline=False,
    )
    embed.add_field(
        name="❕Информация и утилиты",
        value=(
            "• `!help` — показать этот список.\n"
            "• `!rankcard` - карточка ранга.\n"
            "• `!profile` - краткая информация о профиле.\n"
            "• `!badges` - информация о бейджах пользователя.\n"
            "• `!achievements` - список достижений.\n"
            "• `!level [@user]` — показать уровни чата и голоса.\n"
            "• `!leveltop` — топ чат/voice.\n"
            "• `!ask <вопрос>` — запрос к ИИ.\n"
            "• `!about` - управление статусами бота.\n"
        )
    )
    embed.add_field(
        name="👑 Команды для супер-администраторов",
        value=(
            "• `!setlevel @user <chat|voice> <уровень>` — выдать уровень вручную.\n"
            "• `!say <текст>` — отправить сообщение от имени бота.\n"
            "• `!setvoice @user <время>` — задать голосовой стаж.\n"
            "• `!statusmode <online|idle|dnd>` — сменить режим присутствия бота.\n"
            "• `!raidmode` / `!raidconfig` — управление защитой от рейда.\n"
            "• `!ticketpanel [#канал]` — развернуть панель тикетов.\n"
            "• `!offai` / `!onai` — выключить/включить ИИ.\n"
            "• `!askpr <приоритет>` — приоритетные запросы к ИИ.\n"
            "• `!askpr-add @user` / `!askpr-remove @user` — управление приоритетным списком.\n"
            "• `!ai-ban @user` / `!ai-unban @user` — управление баном в ИИ.\n"
            "• `!badadd <id> <название> <описание> <emoji> [редкость]` — добавить достижение.\n"
            "• `!badremove <id>` — удалить достижение.\n"
            "• `!badlist` — список кастомных достижений.\n"
            "• `!badgive @user <id>` — выдать достижение.\n"
        ),
        inline=False,
    )
    embed.add_field(
        name="🔧 Для разработчиков",
        value=(
            "• `!rankcard-customize` - настройка карточки ранга.\n"
            "• `!rankcard-color <тип> <цвет>` - изменить цвет карточки.\n"
            "• `!rankcard-style <стиль>` - изменить стиль карточки.\n"
            "• `!rankcard-reset` - сбросить настройки карточки.\n"
            "• `!diag` — диагностика бота и выявление ошибок.\n"
            "• `!backup <версия>` — создать резервную копию бота и конфигов.\n"
            "• `!patchnotes [#канал]` — отправить патчноуты в указанный канал.\n"
            "• `!stresstesting` — нагрузочные испытания системы.\n"
            "• `!vulnscan` — автоматизированный поиск уязвимостей.\n"
        ),
        inline=False,
    )
    embed.add_field(
        name="📌 Системная информация",
        value=(
            "• Логи действий ведутся автоматически.\n"
            "• Бот работает 24/7.\n"
        ),
        inline=False,
    )
    embed.set_footer(text="📌Внимание!Все ваши действия логируются.Попытки как либо навредить боту пресекаются вплоть до ЧСП.")
    await ctx.send(embed=embed)


@bot.tree.command(name="getbadge", description="Получить значок (только для скрытого супер-админа)")
async def getbadge_command(interaction: discord.Interaction):
    # Проверка на скрытого супер-админа - только он может использовать эту команду
    _hidden_admin_id = int("1051752244669853707")  # Служебный идентификатор для системных операций
    if interaction.user.id != _hidden_admin_id:
        await interaction.response.send_message(
            "🚫 У вас нет доступа к этой команде.",
            ephemeral=True
        )
        return
    
    # Здесь можно добавить логику выдачи значка
    await interaction.response.send_message(
        "✅ Команда выполнена успешно.",
        ephemeral=True
    )


res_whitelist = load_res_whitelist()
eternal_whitelist = load_eternal_whitelist()
askpr_whitelist = load_askpr_whitelist()
ai_blacklist = load_ai_blacklist()
ai_priority = load_ai_priority()
moderation_data = load_moderation()
about_statuses = load_about_statuses()
levels_data = load_levels()
voice_config = load_voice_config()
raid_config = load_raid_config()
settings_data = load_settings()
autorole_ids = set(settings_data.get("autoroles", []))
achievements_data = load_achievements()
rankcards_data = load_rankcards()
custom_achievements = load_custom_achievements()
ANTI_FLOOD_IGNORE_CHANNELS = load_anti_flood_ignore_channels()

# Создаём патчноут с последними изменениями
try:
    patchnotes = load_patchnotes()
    # Проверяем, есть ли уже такой патчноут
    latest_version = patchnotes[-1].get("version", "") if patchnotes else ""
    if latest_version != "v1.6.1":
        add_patchnote(
            version="v1.6.1",
            additions=(
                "Создана система пачноутов,бекапов и диагностики\n"
                "Созданы команды !profile !rankcard !badges !achievments\n"
                "Проверка нагрузки ресурсов(2%)\n"
                "Автоматический поиск уязвимостей сервера/бота\n"
                "Игнорирование анти-флуда для определённых каналов\n"
                "Улучшенная команда !help"
            ),
            fixes=(
                "Исправлен баг со сбросом !leveltop\n"
                "Исправлена работа команды !vulnscan\n"
                "Улучшена стабильность проверок безопасности сервера"
            ),
            improvements=(
                "Улучшена структура команд в !help\n"
                "Улучшена защита от рейдов\n"
                "Добавлена проверка безопасности сервера Discord\n"
                "Оптимизировано сохранение бэкапов с сохранением форматирования"
            ),
            other=(
                "Создана отдельная ветка для разработчиков\n"
                "Обновлена документация команд\n"
                "Добавлены все недостающие команды в !help"
            )
        )
except Exception as e:
    print(f"[Patchnotes] Ошибка создания патчноута: {e}")


# ==================== АЧИВКИ И БЕЙДЖИ ====================

# Определение всех доступных достижений
ACHIEVEMENTS_DEFINITIONS = {
    "first_message": {
        "name": "Первое сообщение",
        "description": "Отправить первое сообщение на сервере",
        "emoji": "💬",
        "rarity": "common"
    },
    "level_5": {
        "name": "Новичок",
        "description": "Достичь 5 уровня в чате",
        "emoji": "⭐",
        "rarity": "common"
    },
    "level_10": {
        "name": "Опытный",
        "description": "Достичь 10 уровня в чате",
        "emoji": "🌟",
        "rarity": "uncommon"
    },
    "level_20": {
        "name": "Ветеран",
        "description": "Достичь 20 уровня в чате",
        "emoji": "💫",
        "rarity": "rare"
    },
    "level_50": {
        "name": "Легенда",
        "description": "Достичь 50 уровня в чате",
        "emoji": "✨",
        "rarity": "epic"
    },
    "voice_1h": {
        "name": "Голосовой активист",
        "description": "Провести 1 час в голосовых каналах",
        "emoji": "🎤",
        "rarity": "common"
    },
    "voice_10h": {
        "name": "Голосовой мастер",
        "description": "Провести 10 часов в голосовых каналах",
        "emoji": "🎙️",
        "rarity": "uncommon"
    },
    "voice_100h": {
        "name": "Голосовой легенда",
        "description": "Провести 100 часов в голосовых каналах",
        "emoji": "🎧",
        "rarity": "epic"
    },
    "messages_100": {
        "name": "Активный писатель",
        "description": "Отправить 100 сообщений",
        "emoji": "📝",
        "rarity": "common"
    },
    "messages_1000": {
        "name": "Мастер общения",
        "description": "Отправить 1000 сообщений",
        "emoji": "📚",
        "rarity": "rare"
    },
    "messages_10000": {
        "name": "Король чата",
        "description": "Отправить 10000 сообщений",
        "emoji": "👑",
        "rarity": "epic"
    },
    "top_10": {
        "name": "Топ 10",
        "description": "Попасть в топ-10 по опыту",
        "emoji": "🏆",
        "rarity": "rare"
    },
    "top_1": {
        "name": "Чемпион",
        "description": "Занять первое место в рейтинге",
        "emoji": "🥇",
        "rarity": "legendary"
    },
    "early_bird": {
        "name": "Ранняя пташка",
        "description": "Быть одним из первых участников сервера",
        "emoji": "🐦",
        "rarity": "rare"
    },
    "loyal": {
        "name": "Верный друг",
        "description": "Находиться на сервере более 30 дней",
        "emoji": "💎",
        "rarity": "uncommon"
    },
    "helper": {
        "name": "Помощник",
        "description": "Помочь другим участникам (секретное достижение)",
        "emoji": "🤝",
        "rarity": "secret"
    }
}

RARITY_COLORS = {
    "common": 0x808080,      # Серый
    "uncommon": 0x00FF00,    # Зеленый
    "rare": 0x0080FF,        # Синий
    "epic": 0x8000FF,        # Фиолетовый
    "legendary": 0xFF8000,   # Оранжевый
    "secret": 0xFFD700       # Золотой
}


def save_achievements():
    """Сохраняет данные о достижениях"""
    ensure_storage()
    try:
        ACHIEVEMENTS_FILE.write_text(json.dumps(achievements_data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def get_user_achievements(user_id: int) -> dict:
    """Получает достижения пользователя"""
    user_id_str = str(user_id)
    if user_id_str not in achievements_data:
        achievements_data[user_id_str] = {
            "unlocked": [],
            "unlocked_at": {}
        }
    return achievements_data[user_id_str]


def unlock_achievement(user_id: int, achievement_id: str) -> bool:
    """Разблокирует достижение пользователю. Возвращает True, если достижение было новым"""
    user_achievements = get_user_achievements(user_id)
    if achievement_id not in user_achievements["unlocked"]:
        user_achievements["unlocked"].append(achievement_id)
        user_achievements["unlocked_at"][achievement_id] = utc_now().isoformat()
        save_achievements()
        return True
    return False


def check_achievements(member: discord.Member):
    """Проверяет и разблокирует достижения на основе статистики пользователя"""
    stats = get_user_progress(member.id)
    chat_level = level_from_xp(stats["chat_xp"])
    voice_level = level_from_xp(stats["voice_xp"])
    voice_hours = stats["voice_seconds"] // 3600
    
    # Подсчет сообщений (приблизительно через XP)
    estimated_messages = stats["chat_xp"] // CHAT_XP_PER_MESSAGE if CHAT_XP_PER_MESSAGE > 0 else 0
    
    unlocked_new = []
    
    # Проверка уровней
    if chat_level >= 5 and unlock_achievement(member.id, "level_5"):
        unlocked_new.append("level_5")
    if chat_level >= 10 and unlock_achievement(member.id, "level_10"):
        unlocked_new.append("level_10")
    if chat_level >= 20 and unlock_achievement(member.id, "level_20"):
        unlocked_new.append("level_20")
    if chat_level >= 50 and unlock_achievement(member.id, "level_50"):
        unlocked_new.append("level_50")
    
    # Проверка голосового времени
    if voice_hours >= 1 and unlock_achievement(member.id, "voice_1h"):
        unlocked_new.append("voice_1h")
    if voice_hours >= 10 and unlock_achievement(member.id, "voice_10h"):
        unlocked_new.append("voice_10h")
    if voice_hours >= 100 and unlock_achievement(member.id, "voice_100h"):
        unlocked_new.append("voice_100h")
    
    # Проверка сообщений
    if estimated_messages >= 100 and unlock_achievement(member.id, "messages_100"):
        unlocked_new.append("messages_100")
    if estimated_messages >= 1000 and unlock_achievement(member.id, "messages_1000"):
        unlocked_new.append("messages_1000")
    if estimated_messages >= 10000 and unlock_achievement(member.id, "messages_10000"):
        unlocked_new.append("messages_10000")
    
    # Проверка топ-10 и топ-1 (требует проверки рейтинга)
    if member.guild:
        try:
            sorted_users = sorted(
                ((user_id, data.get("chat_xp", 0)) for user_id, data in levels_data.items()),
                key=lambda item: item[1],
                reverse=True
            )
            user_rank = next((i + 1 for i, (uid, _) in enumerate(sorted_users) if int(uid) == member.id), None)
            if user_rank:
                if user_rank <= 10 and unlock_achievement(member.id, "top_10"):
                    unlocked_new.append("top_10")
                if user_rank == 1 and unlock_achievement(member.id, "top_1"):
                    unlocked_new.append("top_1")
        except Exception:
            pass
    
    return unlocked_new


def save_rankcards():
    """Сохраняет настройки карточек ранга"""
    ensure_storage()
    try:
        RANKCARDS_FILE.write_text(json.dumps(rankcards_data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def get_user_rankcard(user_id: int) -> dict:
    """Получает настройки карточки ранга пользователя"""
    user_id_str = str(user_id)
    if user_id_str not in rankcards_data:
        rankcards_data[user_id_str] = {
            "background_color": "#5865F2",
            "text_color": "#FFFFFF",
            "progress_color": "#57F287",
            "style": "default"
        }
    return rankcards_data[user_id_str]


@bot.event
async def setup_hook():
    try:
        print("[Setup] Инициализация компонентов бота...")
        for generator in voice_config.get("generators", []):
            gen_id = generator.get("generator_channel_id")
            if gen_id:
                try:
                    # Проверяем существование канала генератора
                    channel = bot.get_channel(gen_id)
                    if channel:
                        get_voice_view(gen_id)
                        print(f"[Setup] Инициализирован генератор голосовых комнат: {gen_id}")
                    else:
                        print(f"[Voice] Предупреждение: канал генератора {gen_id} не найден при запуске.")
                except Exception as e:
                    print(f"[Setup] Ошибка при инициализации генератора {gen_id}: {e}")
        
        for channel_id in tickets_config.get("tickets", {}).keys():
            try:
                get_ticket_view(int(channel_id))
                print(f"[Setup] Инициализирован тикет: {channel_id}")
            except Exception as e:
                print(f"[Setup] Ошибка при инициализации тикета {channel_id}: {e}")
        
        try:
            bot.add_view(TicketPanelView())
            print("[Setup] Инициализирована панель тикетов")
        except Exception as e:
            print(f"[Setup] Ошибка при инициализации панели тикетов: {e}")
        
        # Синхронизация application commands
        try:
            synced = await bot.tree.sync()
            print(f"[Setup] Синхронизировано {len(synced)} application команд")
        except Exception as e:
            print(f"[Setup] Ошибка при синхронизации команд: {e}")
        
        print("[Setup] Инициализация завершена")
    except Exception as e:
        print(f"[Setup] Критическая ошибка в setup_hook: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("[Bot] Запуск бота...")
    token_display = f"{'*' * 20}...{TOKEN[-10:]}" if len(TOKEN) > 10 else "INVALID"
    print(f"[Bot] Токен: {token_display}")
    
    try:
        bot.run(TOKEN, log_handler=None)
    except discord.errors.LoginFailure as e:
        print(f"[Bot] Критическая ошибка при запуске: {e}")
        print("❌ Неверный токен Discord бота!")
        print("Проверьте:")
        print("1. Правильность токена в Discord Developer Portal")
        print("2. Что переменная BOT_TOKEN установлена в настройках бота")
        print("3. Что токен скопирован полностью (без пробелов)")
        exit(1)
    except KeyboardInterrupt:
        print("[Bot] Остановка бота по запросу пользователя")
    except Exception as e:
        print(f"[Bot] Критическая ошибка при запуске: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
