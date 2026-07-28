"""
บอท Discord พื้นฐาน - ตัวอย่างเริ่มต้น
ใช้ไลบรารี discord.py

วิธีใช้:
1. ติดตั้งไลบรารี: pip install discord.py python-dotenv
2. สร้างไฟล์ .env แล้วใส่ DISCORD_TOKEN=โทเคนของคุณ
3. รันไฟล์นี้: python bot.py
"""

import os
import json
import datetime
import discord
from discord.ext import commands
from dotenv import load_dotenv

# โหลดค่าจากไฟล์ .env (เก็บ Token แยกจากโค้ด เพื่อความปลอดภัย)
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
LEGACY_LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))  # ใช้เป็นค่า fallback สำหรับเซิร์ฟเวอร์เดิมเท่านั้น

UNVERIFIED_ROLE_NAME = "Unverified"
VERIFIED_ROLE_NAME = "Verified"
BOT_ADMIN_ROLE_NAME = "Bot Admin"  # role ที่เจ้าของเซิร์ฟใช้แต่งตั้งให้คนอื่นใช้คำสั่ง moderation ได้
DEVELOPER_CREDIT = os.getenv("DEVELOPER_CREDIT", "ACER")  # ชื่อ/แท็กผู้พัฒนาที่จะโชว์ในคู่มือ ตั้งค่าเองได้ผ่าน .env

# ========== ระบบตั้งค่าแยกตามเซิร์ฟเวอร์ (multi-server support) ==========
# แต่ละเซิร์ฟเวอร์ตั้งช่อง log ของตัวเองได้ผ่านคำสั่ง !setlog เก็บไว้ในไฟล์นี้
# CONFIG_DIR: ถ้าตั้งค่า env var นี้ไว้ (เช่น mount Railway Volume ที่ /data) ไฟล์จะไม่หายตอน deploy ใหม่
# ถ้าไม่ได้ตั้ง จะเก็บไว้ข้างไฟล์ bot.py เหมือนเดิม (จะหายเมื่อ deploy ใหม่บน Railway ถ้าไม่มี Volume)
CONFIG_DIR = os.getenv("CONFIG_DIR", os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(CONFIG_DIR, "guild_config.json")


def load_all_config():
    """โหลด config ทั้งหมดของทุกเซิร์ฟเวอร์จากไฟล์ JSON"""
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_all_config(data):
    """เซฟ config ทั้งหมดกลับลงไฟล์ JSON"""
    os.makedirs(CONFIG_DIR, exist_ok=True)  # เผื่อโฟลเดอร์ (เช่น /data) ยังไม่ถูกสร้าง
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_log_channel_id(guild_id):
    """คืนค่า channel ID ของช่อง log ที่ตั้งไว้เฉพาะเซิร์ฟเวอร์นี้ (None ถ้ายังไม่ได้ตั้ง)"""
    data = load_all_config()
    guild_conf = data.get(str(guild_id))
    if guild_conf and guild_conf.get("log_channel_id"):
        return guild_conf["log_channel_id"]
    return None


def set_log_channel_id(guild_id, channel_id):
    """ตั้งค่าช่อง log ของเซิร์ฟเวอร์นี้ แล้วเซฟลงไฟล์"""
    data = load_all_config()
    guild_conf = data.setdefault(str(guild_id), {})
    guild_conf["log_channel_id"] = channel_id
    save_all_config(data)


# ========== ระบบเก็บสถิติ Warn (แยกไฟล์จาก guild_config.json) ==========
# โครงสร้าง: { "guild_id": { "user_id": [ {reason, moderator_id, moderator_name, timestamp}, ... ] } }
WARN_FILE = os.path.join(CONFIG_DIR, "warnings.json")

WARN_MUTE_THRESHOLD = 3   # ครบ 3 ครั้ง -> auto-mute
WARN_MUTE_MINUTES = 30    # ระยะเวลา auto-mute (นาที)
WARN_KICK_THRESHOLD = 5   # ครบ 5 ครั้ง -> auto-kick


def load_all_warnings():
    """โหลดข้อมูล warn ทั้งหมดของทุกเซิร์ฟเวอร์จากไฟล์ JSON"""
    if not os.path.exists(WARN_FILE):
        return {}
    try:
        with open(WARN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_all_warnings(data):
    """เซฟข้อมูล warn ทั้งหมดกลับลงไฟล์ JSON"""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(WARN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_warning(guild_id, user_id, reason, moderator):
    """เพิ่ม warn ให้สมาชิกคนนี้ แล้วคืนค่าจำนวน warn ทั้งหมดที่มีตอนนี้"""
    data = load_all_warnings()
    guild_warns = data.setdefault(str(guild_id), {})
    user_warns = guild_warns.setdefault(str(user_id), [])
    user_warns.append({
        "reason": reason,
        "moderator_id": moderator.id,
        "moderator_name": str(moderator),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    })
    save_all_warnings(data)
    return len(user_warns)


def get_warnings(guild_id, user_id):
    """คืนค่า list ของ warn ทั้งหมดของสมาชิกคนนี้ (list ว่างถ้าไม่มี)"""
    data = load_all_warnings()
    return data.get(str(guild_id), {}).get(str(user_id), [])


def clear_warnings(guild_id, user_id):
    """ล้าง warn ทั้งหมดของสมาชิกคนนี้ คืนค่าจำนวนที่ถูกล้างไป"""
    data = load_all_warnings()
    guild_warns = data.setdefault(str(guild_id), {})
    count = len(guild_warns.get(str(user_id), []))
    guild_warns[str(user_id)] = []
    save_all_warnings(data)
    return count


# ========== ระบบ Reaction Role (แยกไฟล์) ==========
# โครงสร้าง: { "message_id": { "channel_id": int, "roles": { "emoji": role_id, ... } } }
REACTION_ROLE_FILE = os.path.join(CONFIG_DIR, "reaction_roles.json")


def load_reaction_roles():
    if not os.path.exists(REACTION_ROLE_FILE):
        return {}
    try:
        with open(REACTION_ROLE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_reaction_roles(data):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(REACTION_ROLE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ========== ระบบ Poll (แยกไฟล์) ==========
# โครงสร้าง: { "message_id": { "channel_id": int, "question": str, "options": [str,...],
#              "emojis": [str,...], "closed": bool } }
POLL_FILE = os.path.join(CONFIG_DIR, "polls.json")


def load_polls():
    if not os.path.exists(POLL_FILE):
        return {}
    try:
        with open(POLL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_polls(data):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(POLL_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


NUMBER_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]

# แคชยอดใช้งาน invite ของแต่ละเซิร์ฟเวอร์ไว้ในหน่วยความจำ (ไม่ต้องเซฟลงไฟล์ เพราะโหลดใหม่จาก Discord ได้ตอนสตาร์ท)
# โครงสร้าง: { guild_id: { invite_code: uses_count } }
invite_cache = {}


async def refresh_invite_cache(guild):
    """ดึงยอดใช้งาน invite ปัจจุบันทั้งหมดของเซิร์ฟเวอร์นี้มาเก็บไว้เทียบ"""
    try:
        invites = await guild.invites()
        invite_cache[guild.id] = {inv.code: inv.uses for inv in invites}
    except discord.Forbidden:
        invite_cache[guild.id] = {}
        print(f"⚠️ [Invite] บอทไม่มีสิทธิ์ Manage Server ในเซิร์ฟเวอร์ '{guild.name}' — ระบบติดตาม invite จะไม่ทำงาน")


# ตั้งค่า Intents (สิทธิ์การเข้าถึงข้อมูลต่างๆ)
intents = discord.Intents.default()
intents.message_content = True  # จำเป็นถ้าต้องการให้บอทอ่านเนื้อหาข้อความ
intents.members = True  # จำเป็นสำหรับ on_member_join/on_member_remove (ต้องไปเปิด "SERVER MEMBERS INTENT" ใน Discord Developer Portal ด้วย)

# สร้างบอท โดยใช้ "!" เป็นคำนำหน้าคำสั่ง (เปลี่ยนได้ตามต้องการ)
bot = commands.Bot(command_prefix="!", intents=intents)


async def send_log(guild, embed):
    """ส่ง embed ไปที่ช่อง log ของเซิร์ฟเวอร์นี้ (ตั้งค่าด้วย !setlog) ถ้ายังไม่ได้ตั้ง จะลอง fallback ไปที่ LOG_CHANNEL_ID เดิมใน .env"""
    log_channel_id = get_log_channel_id(guild.id) or LEGACY_LOG_CHANNEL_ID
    if not log_channel_id:
        print(f"⚠️ [LOG] เซิร์ฟเวอร์ '{guild.name}' ยังไม่ได้ตั้งช่อง log — ใช้คำสั่ง !setlog ในช่องที่ต้องการก่อน")
        return
    channel = guild.get_channel(log_channel_id)
    if channel is None:
        # เผื่อ cache ยังไม่มีช่องนี้ ลอง fetch จาก API โดยตรง
        try:
            channel = await guild.fetch_channel(log_channel_id)
        except discord.NotFound:
            print(f"❌ [LOG] ไม่พบช่อง ID {log_channel_id} ในเซิร์ฟเวอร์ '{guild.name}' "
                  f"— ใช้ !setlog ตั้งช่อง log ใหม่")
            return
        except discord.Forbidden:
            print(f"❌ [LOG] บอทไม่มีสิทธิ์เข้าถึงช่อง ID {log_channel_id}")
            return
    try:
        await channel.send(embed=embed)
    except discord.Forbidden:
        print(f"⚠️ [LOG] ส่ง log ไม่ได้ บอทไม่มีสิทธิ์พูดในช่อง '{channel.name}' "
              f"(เช็ค Server Settings > Roles/Channel Permissions > Send Messages, Embed Links)")
    except Exception as e:
        print(f"❌ [LOG] ส่ง log ไม่สำเร็จ: {e}")


def mod_check(permission_name):
    """
    ใช้แทน @commands.has_permissions(...)
    อนุญาตให้ใช้คำสั่งได้ถ้าตรงข้อใดข้อหนึ่ง:
    - เป็นเจ้าของเซิร์ฟเวอร์
    - มี role "Bot Admin" (แต่งตั้งผ่านคำสั่ง !addadmin)
    - มีสิทธิ์ Discord permission ตามที่ระบุ (เช่น kick_members, ban_members)
    """
    async def predicate(ctx):
        if ctx.guild is None:
            return False
        if ctx.author.id == ctx.guild.owner_id:
            return True
        bot_admin_role = discord.utils.get(ctx.author.roles, name=BOT_ADMIN_ROLE_NAME)
        if bot_admin_role is not None:
            return True
        return getattr(ctx.author.guild_permissions, permission_name, False)
    return commands.check(predicate)


async def get_or_create_role(guild, role_name, color=discord.Color.default()):
    """หา role ตามชื่อ ถ้าไม่มีให้สร้างใหม่"""
    role = discord.utils.get(guild.roles, name=role_name)
    if role is None:
        role = await guild.create_role(name=role_name, color=color, reason="สร้างอัตโนมัติโดยบอท")
    return role


async def send_dm_template(member, title, description, guild=None, extra_fields=None, color=discord.Color.from_rgb(255, 179, 199)):
    """
    ส่ง DM ไปหาสมาชิก โดยใช้รูปแบบ Embed มาตรฐานเดียวกันทุกจุด (ไม่มีรูปภาพ/แบนเนอร์)
    คืนค่า True ถ้าส่งสำเร็จ, False ถ้าส่งไม่ได้ (เช่นปิดรับ DM)
    """
    embed = discord.Embed(title=title, description=description, color=color)
    embed.add_field(name="🍓 คุณ", value=member.mention, inline=False)
    if guild is not None:
        embed.add_field(name="🍓 เข้ามาคนที่", value=str(guild.member_count), inline=False)
    if extra_fields:
        for name, value in extra_fields:
            embed.add_field(name=name, value=value, inline=False)
    try:
        await member.send(embed=embed)
        return True
    except discord.Forbidden:
        return False


@bot.event
async def on_ready():
    """เรียกใช้เมื่อบอทออนไลน์และพร้อมทำงาน"""
    print(f"✅ บอทออนไลน์แล้ว: {bot.user}")
    print(f"เชื่อมต่อกับ {len(bot.guilds)} เซิร์ฟเวอร์")

    # ดึงข้อมูลเจ้าของแอปบอท (คนที่สร้างบอทใน Developer Portal) ไว้ใช้กับคำสั่ง !report
    try:
        app_info = await bot.application_info()
        owner = app_info.team.owner if app_info.team else app_info.owner
        bot.dev_owner_id = owner.id
        print(f"✅ เจ้าของบอท (รับรายงานปัญหา): {owner} (ID: {owner.id})")
    except Exception as e:
        bot.dev_owner_id = None
        print(f"⚠️ ดึงข้อมูลเจ้าของบอทไม่ได้: {e} — คำสั่ง !report จะใช้งานไม่ได้")

    # เช็คสถานะช่อง log ของแต่ละเซิร์ฟเวอร์ทันทีตอนสตาร์ท + เตรียมแคช invite
    for guild in bot.guilds:
        log_channel_id = get_log_channel_id(guild.id) or LEGACY_LOG_CHANNEL_ID
        if not log_channel_id:
            print(f"⚠️ [{guild.name}] ยังไม่ได้ตั้งช่อง log — ให้แอดมินพิมพ์ !setlog ในช่องที่ต้องการ")
            continue
        channel = guild.get_channel(log_channel_id)
        if channel:
            print(f"✅ [{guild.name}] ช่อง log: #{channel.name}")
        else:
            print(f"❌ [{guild.name}] ตั้งช่อง log ไว้ (ID {log_channel_id}) แต่หาช่องนี้ไม่เจอ — ใช้ !setlog ตั้งใหม่")

        await refresh_invite_cache(guild)


@bot.event
async def on_member_join(member):
    """เมื่อสมาชิกใหม่เข้าเซิร์ฟเวอร์: ให้ role Unverified และแจ้งวิธียืนยันตัวตน"""
    guild = member.guild

    # มอบ role Unverified ให้สมาชิกใหม่
    try:
        unverified_role = await get_or_create_role(guild, UNVERIFIED_ROLE_NAME, discord.Color.greyple())
        await member.add_roles(unverified_role, reason="สมาชิกใหม่ - รอยืนยันตัวตน")
    except discord.Forbidden:
        print("⚠️ บอทไม่มีสิทธิ์จัดการ Role กรุณาเช็คสิทธิ์ Manage Roles")

    # ส่ง DM ต้อนรับ พร้อมอธิบายวิธียืนยันตัวตน
    dm_sent = await send_dm_template(
        member,
        title="🍓 WELCOME TO SERVER 👋",
        description=(
            f"ยินดีต้อนรับเข้าสู่ **{guild.name}** ค่ะ!\n\n"
            f"เพื่อเข้าถึงช่องแชทต่างๆ ในเซิร์ฟเวอร์ กรุณายืนยันตัวตนก่อน โดย:\n"
            f"1️⃣ กลับไปที่เซิร์ฟเวอร์ **{guild.name}**\n"
            f"2️⃣ พิมพ์คำสั่ง `!verify` ในช่องแชทที่เปิดให้ใช้งานได้\n"
            f"3️⃣ ระบบจะยืนยันตัวตนให้อัตโนมัติ แล้วคุณจะเห็นช่องแชททั้งหมด\n\n"
            f"ถ้ามีปัญหาติดต่อแอดมินได้เลยค่ะ 💗"
        ),
        guild=guild,
    )

    # ทักทายในช่อง system channel ด้วย (เผื่อ DM ส่งไม่ได้)
    if guild.system_channel:
        note = "" if dm_sent else " (ส่ง DM ไม่ได้ โปรดเปิดรับข้อความส่วนตัว)"
        await guild.system_channel.send(
            f"ยินดีต้อนรับ {member.mention} เข้าสู่เซิร์ฟเวอร์! 🎉\n"
            f"กรุณาพิมพ์ `!verify` เพื่อยืนยันตัวตนก่อนใช้งานช่องอื่นๆ ครับ{note}"
        )

    # เช็คว่าเข้ามาด้วย invite ลิงก์ไหน (เทียบยอดใช้งานก่อน-หลัง)
    inviter_text = "ไม่ทราบ (อาจเป็น Vanity URL หรือบอทไม่มีสิทธิ์ Manage Server)"
    try:
        before_counts = invite_cache.get(guild.id, {})
        after_invites = await guild.invites()
        after_counts = {inv.code: inv.uses for inv in after_invites}
        used_invite = None
        for inv in after_invites:
            if inv.uses is not None and inv.uses > before_counts.get(inv.code, 0):
                used_invite = inv
                break
        if used_invite:
            inviter_name = str(used_invite.inviter) if used_invite.inviter else "ไม่ทราบ"
            inviter_text = f"{inviter_name} (โค้ด `{used_invite.code}`, ใช้ไปแล้ว {used_invite.uses} ครั้ง)"
        invite_cache[guild.id] = after_counts
    except discord.Forbidden:
        pass

    # บันทึก log
    embed = discord.Embed(
        title="📥 สมาชิกใหม่เข้าเซิร์ฟเวอร์",
        description=f"{member.mention} ({member})",
        color=discord.Color.green(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="🔗 เชิญโดย", value=inviter_text, inline=False)
    await send_log(guild, embed)


@bot.event
async def on_member_remove(member):
    """บันทึก log เมื่อสมาชิกออกจากเซิร์ฟเวอร์ (ลาออกเอง หรือโดนเตะ/แบน)"""
    embed = discord.Embed(
        title="📤 สมาชิกออกจากเซิร์ฟเวอร์",
        description=f"{member.mention} ({member})",
        color=discord.Color.orange(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    await send_log(member.guild, embed)


@bot.event
async def on_invite_create(invite):
    """บันทึก log เมื่อมีการสร้างลิงก์เชิญใหม่ + อัปเดตแคชไว้ตรวจสอบภายหลัง"""
    guild = invite.guild
    invite_cache.setdefault(guild.id, {})[invite.code] = invite.uses or 0

    embed = discord.Embed(
        title="🔗 สร้างลิงก์เชิญใหม่",
        color=discord.Color.blurple(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.add_field(name="โดยใคร", value=str(invite.inviter) if invite.inviter else "ไม่ทราบ", inline=True)
    embed.add_field(name="โค้ด", value=f"`{invite.code}`", inline=True)
    embed.add_field(name="ช่อง", value=invite.channel.mention if invite.channel else "ไม่ทราบ", inline=True)
    embed.add_field(
        name="อายุลิงก์",
        value="ไม่หมดอายุ" if invite.max_age == 0 else f"{invite.max_age} วินาที",
        inline=True,
    )
    embed.add_field(
        name="จำนวนใช้ได้",
        value="ไม่จำกัด" if invite.max_uses == 0 else str(invite.max_uses),
        inline=True,
    )
    await send_log(guild, embed)


@bot.event
async def on_invite_delete(invite):
    """เอา invite ที่ถูกลบออกจากแคช กันข้อมูลเก่าค้าง"""
    invite_cache.get(invite.guild.id, {}).pop(invite.code, None)


@bot.event
async def on_message_delete(message):
    """บันทึก log เมื่อข้อความถูกลบ (ข้ามข้อความของบอทเอง)"""
    if message.author.bot:
        return
    embed = discord.Embed(
        title="🗑️ ข้อความถูกลบ",
        color=discord.Color.red(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.add_field(name="ผู้เขียน", value=f"{message.author.mention}", inline=True)
    embed.add_field(name="ช่อง", value=f"{message.channel.mention}", inline=True)
    embed.add_field(name="เนื้อหา", value=(message.content or "(ไม่มีข้อความ/เป็นรูปภาพ)")[:1000], inline=False)
    await send_log(message.guild, embed)


@bot.event
async def on_message_edit(before, after):
    """บันทึก log เมื่อข้อความถูกแก้ไข (ข้ามข้อความของบอทเอง และข้ามถ้าเนื้อหาไม่เปลี่ยน เช่น embed โหลดลิงก์)"""
    if before.author.bot:
        return
    if before.content == after.content:
        return
    embed = discord.Embed(
        title="✏️ ข้อความถูกแก้ไข",
        color=discord.Color.blue(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.add_field(name="ผู้เขียน", value=f"{before.author.mention}", inline=True)
    embed.add_field(name="ช่อง", value=f"{before.channel.mention}", inline=True)
    embed.add_field(name="ก่อนแก้", value=(before.content or "(ว่าง)")[:1000], inline=False)
    embed.add_field(name="หลังแก้", value=(after.content or "(ว่าง)")[:1000], inline=False)
    if before.guild:
        await send_log(before.guild, embed)


@bot.event
async def on_voice_state_update(member, before, after):
    """บันทึก log เมื่อมีคนเข้า/ออก/ย้ายห้องเสียง (VC)"""
    guild = member.guild

    if before.channel is None and after.channel is not None:
        # เข้าห้องเสียง
        embed = discord.Embed(
            title="🔊 เข้าห้องเสียง",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.add_field(name="สมาชิก", value=member.mention, inline=True)
        embed.add_field(name="ห้อง", value=after.channel.mention, inline=True)
        await send_log(guild, embed)

    elif before.channel is not None and after.channel is None:
        # ออกจากห้องเสียง
        embed = discord.Embed(
            title="🔇 ออกจากห้องเสียง",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.add_field(name="สมาชิก", value=member.mention, inline=True)
        embed.add_field(name="ห้อง", value=before.channel.mention, inline=True)
        await send_log(guild, embed)

    elif before.channel is not None and after.channel is not None and before.channel.id != after.channel.id:
        # ย้ายห้องเสียง
        embed = discord.Embed(
            title="🔀 ย้ายห้องเสียง",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.add_field(name="สมาชิก", value=member.mention, inline=True)
        embed.add_field(name="จาก", value=before.channel.mention, inline=True)
        embed.add_field(name="ไปที่", value=after.channel.mention, inline=True)
        await send_log(guild, embed)


@bot.event
async def on_member_update(before, after):
    """บันทึก log เมื่อ: เปลี่ยนชื่อเล่น / role เปลี่ยนแปลง / เพิ่งบูสต์เซิร์ฟ"""
    guild = after.guild

    # เปลี่ยนชื่อเล่น
    if before.nick != after.nick:
        embed = discord.Embed(
            title="✏️ เปลี่ยนชื่อเล่น",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.add_field(name="สมาชิก", value=after.mention, inline=True)
        embed.add_field(name="ชื่อเดิม", value=before.nick or "(ไม่มี/ใช้ชื่อ username)", inline=True)
        embed.add_field(name="ชื่อใหม่", value=after.nick or "(ไม่มี/ใช้ชื่อ username)", inline=True)
        await send_log(guild, embed)

    # Role เปลี่ยนแปลง
    before_roles = set(before.roles)
    after_roles = set(after.roles)
    added_roles = after_roles - before_roles
    removed_roles = before_roles - after_roles
    if added_roles or removed_roles:
        embed = discord.Embed(
            title="🎭 Role ของสมาชิกเปลี่ยนแปลง",
            color=discord.Color.teal(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.add_field(name="สมาชิก", value=after.mention, inline=False)
        if added_roles:
            embed.add_field(name="➕ เพิ่ม", value=", ".join(r.mention for r in added_roles), inline=True)
        if removed_roles:
            embed.add_field(name="➖ ถอด", value=", ".join(r.mention for r in removed_roles), inline=True)
        await send_log(guild, embed)

    # เพิ่งบูสต์เซิร์ฟ (premium_since เปลี่ยนจาก None -> มีค่า)
    if before.premium_since is None and after.premium_since is not None:
        embed = discord.Embed(
            title="🚀 มีคน Boost เซิร์ฟเวอร์!",
            description=f"{after.mention} เพิ่ง boost เซิร์ฟเวอร์นี้ ขอบคุณมากๆ ค่ะ 💗",
            color=discord.Color.pink(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        await send_log(guild, embed)


@bot.event
async def on_raw_reaction_add(payload):
    """ระบบ Reaction Role: กดอิโมจิเพื่อรับ role (เลือกได้แค่ 1 อันต่อเมนู)"""
    if payload.member is None or payload.member.bot:
        return

    data = load_reaction_roles()
    conf = data.get(str(payload.message_id))
    if not conf:
        return

    emoji_str = str(payload.emoji)
    role_id = conf["roles"].get(emoji_str)
    if not role_id:
        return

    guild = bot.get_guild(payload.guild_id)
    if guild is None:
        return
    role = guild.get_role(role_id)
    member = payload.member
    if role is None:
        return

    try:
        await member.add_roles(role, reason="Reaction Role")
    except discord.Forbidden:
        print(f"❌ [ReactionRole] บอทไม่มีสิทธิ์เพิ่ม role '{role.name}' ให้ {member}")
        return

    # เลือกได้แค่ 1 อันต่อเมนู: เอา reaction อื่นของคนนี้ในเมนูเดียวกันออก
    # (การลบ reaction จะไปสั่ง on_raw_reaction_remove ให้ถอด role เก่าให้เองอัตโนมัติ)
    channel = guild.get_channel(conf["channel_id"])
    if channel is None:
        try:
            channel = await guild.fetch_channel(conf["channel_id"])
        except (discord.NotFound, discord.Forbidden):
            return
    try:
        message = await channel.fetch_message(payload.message_id)
    except (discord.NotFound, discord.Forbidden):
        return

    for other_emoji in conf["roles"]:
        if other_emoji == emoji_str:
            continue
        try:
            await message.remove_reaction(other_emoji, member)
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            pass


@bot.event
async def on_raw_reaction_remove(payload):
    """ระบบ Reaction Role: เอาอิโมจิออก = ถอด role ออกด้วย"""
    data = load_reaction_roles()
    conf = data.get(str(payload.message_id))
    if not conf:
        return

    emoji_str = str(payload.emoji)
    role_id = conf["roles"].get(emoji_str)
    if not role_id:
        return

    guild = bot.get_guild(payload.guild_id)
    if guild is None:
        return
    role = guild.get_role(role_id)
    member = guild.get_member(payload.user_id)
    if role is None or member is None or member.bot:
        return

    try:
        await member.remove_roles(role, reason="Reaction Role: เอาออก")
    except discord.Forbidden:
        print(f"❌ [ReactionRole] บอทไม่มีสิทธิ์ถอด role '{role.name}' จาก {member}")


IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")


@bot.event
async def on_message(message):
    """เช็คว่ามีการส่งรูปภาพไหม แล้วบันทึก log พร้อมแนบรูป"""
    if message.author.bot:
        await bot.process_commands(message)
        return

    if message.attachments:
        images = [a for a in message.attachments if a.filename.lower().endswith(IMAGE_EXTENSIONS)]
        if images:
            embed = discord.Embed(
                title="🖼️ มีคนส่งรูปภาพ",
                color=discord.Color.purple(),
                timestamp=datetime.datetime.now(datetime.timezone.utc),
            )
            embed.add_field(name="ผู้ส่ง", value=message.author.mention, inline=True)
            embed.add_field(name="ช่อง", value=message.channel.mention, inline=True)
            if len(images) > 1:
                embed.add_field(name="จำนวนรูป", value=str(len(images)), inline=True)
            embed.set_image(url=images[0].url)
            await send_log(message.guild, embed)

    await bot.process_commands(message)


@bot.command(name="verify")
async def verify(ctx):
    """ยืนยันตัวตนเพื่อเข้าถึงเซิร์ฟเวอร์เต็มรูปแบบ พิมพ์ !verify"""
    guild = ctx.guild
    member = ctx.author

    unverified_role = discord.utils.get(guild.roles, name=UNVERIFIED_ROLE_NAME)
    verified_role = await get_or_create_role(guild, VERIFIED_ROLE_NAME, discord.Color.green())

    if verified_role in member.roles:
        await ctx.send(f"{member.mention} คุณยืนยันตัวตนไปแล้วครับ ✅")
        return

    try:
        if unverified_role and unverified_role in member.roles:
            await member.remove_roles(unverified_role)
        await member.add_roles(verified_role)
        await ctx.send(f"✅ ยืนยันตัวตนสำเร็จ! ยินดีต้อนรับ {member.mention}")

        embed = discord.Embed(
            title="✅ ยืนยันตัวตนสำเร็จ",
            description=f"{member.mention} ({member}) ยืนยันตัวตนแล้ว",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        await send_log(guild, embed)
    except discord.Forbidden:
        await ctx.send("❌ บอทไม่มีสิทธิ์จัดการ Role กรุณาแจ้งแอดมิน")


@bot.command(name="ping")
async def ping(ctx):
    """ทดสอบว่าบอทตอบสนองไหม พิมพ์ !ping"""
    latency_ms = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong! ({latency_ms}ms)")


@bot.command(name="hello")
async def hello(ctx):
    """ทักทายผู้ใช้ พิมพ์ !hello"""
    await ctx.send(f"สวัสดีครับ {ctx.author.mention}! 👋")


@bot.command(name="say")
async def say(ctx, *, message: str):
    """ให้บอทพูดตามข้อความที่พิมพ์ เช่น !say สวัสดี"""
    await ctx.send(message)


@bot.command(name="info")
async def info(ctx):
    """แสดงข้อมูลเซิร์ฟเวอร์ พิมพ์ !info"""
    guild = ctx.guild
    embed = discord.Embed(title=f"ข้อมูลเซิร์ฟเวอร์: {guild.name}", color=discord.Color.blue())
    embed.add_field(name="จำนวนสมาชิก", value=guild.member_count, inline=True)
    embed.add_field(name="สร้างเมื่อ", value=guild.created_at.strftime("%d/%m/%Y"), inline=True)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    await ctx.send(embed=embed)


# ========== ระบบ Moderation ==========

@bot.command(name="kick")
@mod_check("kick_members")
async def kick(ctx, member: discord.Member, *, reason: str = "ไม่ระบุเหตุผล"):
    """เตะสมาชิกออกจากเซิร์ฟเวอร์ พิมพ์ !kick @ชื่อ เหตุผล"""
    dm_sent = await send_dm_template(
        member,
        title="👢 คุณถูกเตะออกจากเซิร์ฟเวอร์",
        description=f"คุณถูกเตะออกจากเซิร์ฟเวอร์ **{ctx.guild.name}**",
        extra_fields=[("🍓 เหตุผล", reason)],
    )
    dm_status = "(ส่ง DM แจ้งแล้ว)" if dm_sent else "(ส่ง DM ไม่ได้ อาจปิดรับข้อความส่วนตัว)"
    await member.kick(reason=reason)
    await ctx.send(f"👢 เตะ {member.mention} ออกแล้ว {dm_status}\nเหตุผล: {reason}")

    embed = discord.Embed(
        title="👢 Kick",
        color=discord.Color.orange(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.add_field(name="สมาชิก", value=f"{member} ({member.id})", inline=False)
    embed.add_field(name="โดยใคร", value=ctx.author.mention, inline=True)
    embed.add_field(name="เหตุผล", value=reason, inline=True)
    await send_log(ctx.guild, embed)


@kick.error
async def kick_error(ctx, error):
    if isinstance(error, (commands.MissingPermissions, commands.CheckFailure)):
        await ctx.send("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้ (ต้องมีสิทธิ์ Kick Members หรือ role Bot Admin)")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ หาสมาชิกคนนี้ไม่เจอ")


@bot.command(name="ban")
@mod_check("ban_members")
async def ban(ctx, member: discord.Member, *, reason: str = "ไม่ระบุเหตุผล"):
    """แบนสมาชิกออกจากเซิร์ฟเวอร์ พิมพ์ !ban @ชื่อ เหตุผล"""
    dm_sent = await send_dm_template(
        member,
        title="🔨 คุณถูกแบนออกจากเซิร์ฟเวอร์",
        description=f"คุณถูกแบนออกจากเซิร์ฟเวอร์ **{ctx.guild.name}**",
        extra_fields=[("🍓 เหตุผล", reason)],
    )
    dm_status = "(ส่ง DM แจ้งแล้ว)" if dm_sent else "(ส่ง DM ไม่ได้ อาจปิดรับข้อความส่วนตัว)"
    await member.ban(reason=reason)
    await ctx.send(f"🔨 แบน {member.mention} แล้ว {dm_status}\nเหตุผล: {reason}")

    embed = discord.Embed(
        title="🔨 Ban",
        color=discord.Color.red(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.add_field(name="สมาชิก", value=f"{member} ({member.id})", inline=False)
    embed.add_field(name="โดยใคร", value=ctx.author.mention, inline=True)
    embed.add_field(name="เหตุผล", value=reason, inline=True)
    await send_log(ctx.guild, embed)


@ban.error
async def ban_error(ctx, error):
    if isinstance(error, (commands.MissingPermissions, commands.CheckFailure)):
        await ctx.send("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้ (ต้องมีสิทธิ์ Ban Members หรือ role Bot Admin)")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ หาสมาชิกคนนี้ไม่เจอ")


@bot.command(name="unban")
@mod_check("ban_members")
async def unban(ctx, *, user_input: str):
    """ปลดแบนสมาชิก พิมพ์ !unban ชื่อผู้ใช้ หรือ user ID"""
    banned_users = [entry async for entry in ctx.guild.bans()]
    for ban_entry in banned_users:
        user = ban_entry.user
        if user_input == str(user.id) or user_input.lower() == f"{user.name}".lower():
            await ctx.guild.unban(user)
            await ctx.send(f"✅ ปลดแบน {user.mention} แล้ว")
            return
    await ctx.send("❌ ไม่พบผู้ใช้นี้ในรายชื่อที่ถูกแบน")


@unban.error
async def unban_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้ (ต้องมีสิทธิ์ Ban Members หรือ role Bot Admin)")


@bot.command(name="mute")
@mod_check("moderate_members")
async def mute(ctx, member: discord.Member, minutes: int = 10, *, reason: str = "ไม่ระบุเหตุผล"):
    """ปิดเสียงสมาชิกชั่วคราว พิมพ์ !mute @ชื่อ จำนวนนาที เหตุผล"""
    dm_sent = await send_dm_template(
        member,
        title="🔇 คุณถูกปิดเสียง (Mute)",
        description=f"คุณถูกปิดเสียงในเซิร์ฟเวอร์ **{ctx.guild.name}** เป็นเวลา {minutes} นาที",
        extra_fields=[("🍓 เหตุผล", reason)],
    )
    dm_status = "(ส่ง DM แจ้งแล้ว)" if dm_sent else "(ส่ง DM ไม่ได้ อาจปิดรับข้อความส่วนตัว)"
    duration = datetime.timedelta(minutes=minutes)
    await member.timeout(duration, reason=reason)
    await ctx.send(f"🔇 ปิดเสียง {member.mention} เป็นเวลา {minutes} นาที {dm_status}\nเหตุผล: {reason}")

    embed = discord.Embed(
        title="🔇 Mute (Timeout)",
        color=discord.Color.gold(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.add_field(name="สมาชิก", value=f"{member} ({member.id})", inline=False)
    embed.add_field(name="โดยใคร", value=ctx.author.mention, inline=True)
    embed.add_field(name="ระยะเวลา", value=f"{minutes} นาที", inline=True)
    embed.add_field(name="เหตุผล", value=reason, inline=False)
    await send_log(ctx.guild, embed)


@mute.error
async def mute_error(ctx, error):
    if isinstance(error, (commands.MissingPermissions, commands.CheckFailure)):
        await ctx.send("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้ (ต้องมีสิทธิ์ Moderate Members หรือ role Bot Admin)")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ หาสมาชิกคนนี้ไม่เจอ")


@bot.command(name="unmute")
@mod_check("moderate_members")
async def unmute(ctx, member: discord.Member):
    """ยกเลิกปิดเสียงสมาชิก พิมพ์ !unmute @ชื่อ"""
    await member.timeout(None)
    await ctx.send(f"🔊 ยกเลิกปิดเสียง {member.mention} แล้ว")

    embed = discord.Embed(
        title="🔊 Unmute",
        color=discord.Color.green(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.add_field(name="สมาชิก", value=f"{member} ({member.id})", inline=False)
    embed.add_field(name="โดยใคร", value=ctx.author.mention, inline=True)
    await send_log(ctx.guild, embed)


@unmute.error
async def unmute_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้ (ต้องมีสิทธิ์ Moderate Members หรือ role Bot Admin)")


@bot.command(name="clear")
@mod_check("manage_messages")
async def clear(ctx, amount: int = 5):
    """ลบข้อความในแชท พิมพ์ !clear จำนวน (ค่าเริ่มต้น 5 ข้อความ)"""
    if amount < 1 or amount > 100:
        await ctx.send("❌ กรุณาระบุจำนวนระหว่าง 1-100")
        return
    deleted = await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.send(f"🧹 ลบข้อความไปแล้ว {len(deleted) - 1} ข้อความ")
    await msg.delete(delay=3)


@clear.error
async def clear_error(ctx, error):
    if isinstance(error, (commands.MissingPermissions, commands.CheckFailure)):
        await ctx.send("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้ (ต้องมีสิทธิ์ Manage Messages หรือ role Bot Admin)")


@bot.command(name="warn")
@mod_check("kick_members")
async def warn(ctx, member: discord.Member, *, reason: str = "ไม่ระบุเหตุผล"):
    """เตือนสมาชิก พิมพ์ !warn @ชื่อ เหตุผล (ครบ 3 ครั้ง auto-mute, ครบ 5 ครั้ง auto-kick)"""
    warn_count = add_warning(ctx.guild.id, member.id, reason, ctx.author)

    dm_sent = await send_dm_template(
        member,
        title="⚠️ คุณถูกเตือน",
        description=f"คุณถูกเตือนในเซิร์ฟเวอร์ **{ctx.guild.name}** (ครั้งที่ {warn_count})",
        extra_fields=[("🍓 เหตุผล", reason)],
    )
    dm_status = "(ส่ง DM แจ้งแล้ว)" if dm_sent else "(ส่ง DM ไม่ได้ อาจปิดรับข้อความส่วนตัว)"
    await ctx.send(f"⚠️ เตือน {member.mention} แล้ว (ครั้งที่ {warn_count}) {dm_status}\nเหตุผล: {reason}")

    embed = discord.Embed(
        title="⚠️ Warn",
        color=discord.Color.gold(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.add_field(name="สมาชิก", value=f"{member} ({member.id})", inline=False)
    embed.add_field(name="โดยใคร", value=ctx.author.mention, inline=True)
    embed.add_field(name="เหตุผล", value=reason, inline=True)
    embed.add_field(name="จำนวน warn สะสม", value=str(warn_count), inline=True)
    await send_log(ctx.guild, embed)

    # ตรวจว่าครบเกณฑ์ auto-action หรือยัง (kick เช็คก่อน เพราะเป็นเกณฑ์สูงกว่า)
    if warn_count >= WARN_KICK_THRESHOLD:
        auto_reason = f"ครบ {WARN_KICK_THRESHOLD} warn (auto-kick)"
        await send_dm_template(
            member,
            title="👢 คุณถูกเตะออกจากเซิร์ฟเวอร์ (Auto)",
            description=f"คุณสะสม warn ครบ {WARN_KICK_THRESHOLD} ครั้งในเซิร์ฟเวอร์ **{ctx.guild.name}**",
        )
        try:
            await member.kick(reason=auto_reason)
            await ctx.send(f"👢 {member.mention} ถูกเตะออกอัตโนมัติ เนื่องจากสะสม warn ครบ {WARN_KICK_THRESHOLD} ครั้ง")
            auto_embed = discord.Embed(
                title="👢 Auto-Kick (ครบเกณฑ์ Warn)",
                description=f"{member.mention} ({member}) ถูกเตะออกอัตโนมัติ",
                color=discord.Color.red(),
                timestamp=datetime.datetime.now(datetime.timezone.utc),
            )
            auto_embed.add_field(name="จำนวน warn สะสม", value=str(warn_count), inline=True)
            await send_log(ctx.guild, auto_embed)
        except discord.Forbidden:
            await ctx.send("⚠️ ครบเกณฑ์ auto-kick แล้ว แต่บอทไม่มีสิทธิ์เตะสมาชิกคนนี้")
    elif warn_count >= WARN_MUTE_THRESHOLD:
        auto_reason = f"ครบ {WARN_MUTE_THRESHOLD} warn (auto-mute {WARN_MUTE_MINUTES} นาที)"
        try:
            await member.timeout(datetime.timedelta(minutes=WARN_MUTE_MINUTES), reason=auto_reason)
            await send_dm_template(
                member,
                title="🔇 คุณถูกปิดเสียงอัตโนมัติ (Auto)",
                description=(
                    f"คุณสะสม warn ครบ {WARN_MUTE_THRESHOLD} ครั้งในเซิร์ฟเวอร์ **{ctx.guild.name}** "
                    f"จึงถูกปิดเสียงอัตโนมัติเป็นเวลา {WARN_MUTE_MINUTES} นาที"
                ),
            )
            await ctx.send(f"🔇 {member.mention} ถูกปิดเสียงอัตโนมัติ {WARN_MUTE_MINUTES} นาที เนื่องจากสะสม warn ครบ {WARN_MUTE_THRESHOLD} ครั้ง")
            auto_embed = discord.Embed(
                title="🔇 Auto-Mute (ครบเกณฑ์ Warn)",
                description=f"{member.mention} ({member}) ถูกปิดเสียงอัตโนมัติ {WARN_MUTE_MINUTES} นาที",
                color=discord.Color.gold(),
                timestamp=datetime.datetime.now(datetime.timezone.utc),
            )
            auto_embed.add_field(name="จำนวน warn สะสม", value=str(warn_count), inline=True)
            await send_log(ctx.guild, auto_embed)
        except discord.Forbidden:
            await ctx.send("⚠️ ครบเกณฑ์ auto-mute แล้ว แต่บอทไม่มีสิทธิ์ปิดเสียงสมาชิกคนนี้")


@warn.error
async def warn_error(ctx, error):
    if isinstance(error, (commands.MissingPermissions, commands.CheckFailure)):
        await ctx.send("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้ (ต้องมีสิทธิ์ Kick Members หรือ role Bot Admin)")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ หาสมาชิกคนนี้ไม่เจอ")


@bot.command(name="clearwarnings")
@mod_check("administrator")
async def clearwarnings(ctx, member: discord.Member):
    """ล้างประวัติ warn ทั้งหมดของสมาชิกคนนี้ (เฉพาะเจ้าของเซิร์ฟเวอร์/Bot Admin) พิมพ์ !clearwarnings @ชื่อ"""
    count = clear_warnings(ctx.guild.id, member.id)
    if count == 0:
        await ctx.send(f"{member.mention} ไม่มีประวัติ warn อยู่แล้วครับ")
        return

    await ctx.send(f"✅ ล้างประวัติ warn ของ {member.mention} แล้ว (ลบไป {count} รายการ)")

    embed = discord.Embed(
        title="🧹 ล้างประวัติ Warn",
        description=f"{member.mention} ({member}) ถูกล้างประวัติ warn ({count} รายการ)",
        color=discord.Color.teal(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.add_field(name="โดยใคร", value=ctx.author.mention, inline=True)
    await send_log(ctx.guild, embed)


@clearwarnings.error
async def clearwarnings_error(ctx, error):
    if isinstance(error, (commands.MissingPermissions, commands.CheckFailure)):
        await ctx.send("❌ คำสั่งนี้ใช้ได้เฉพาะเจ้าของเซิร์ฟเวอร์หรือ Bot Admin เท่านั้น")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ หาสมาชิกคนนี้ไม่เจอ")


@bot.command(name="userinfo")
async def userinfo(ctx, member: discord.Member = None):
    """ดูข้อมูลสมาชิกแบบครบ (โปรไฟล์ + role + สถานะ mute + ประวัติ warn) พิมพ์ !userinfo @ชื่อ (ไม่ใส่ = ดูตัวเอง)"""
    member = member or ctx.author
    guild = ctx.guild

    warns = get_warnings(guild.id, member.id)

    embed = discord.Embed(
        title=f"👤 ข้อมูลสมาชิก: {member}",
        color=discord.Color.from_rgb(255, 179, 199),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="🆔 User ID", value=str(member.id), inline=True)
    embed.add_field(name="📅 สร้างบัญชีเมื่อ", value=member.created_at.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(
        name="📥 เข้าเซิร์ฟเวอร์นี้เมื่อ",
        value=member.joined_at.strftime("%d/%m/%Y") if member.joined_at else "ไม่ทราบ",
        inline=True,
    )

    roles = [r.mention for r in member.roles if r.name != "@everyone"]
    embed.add_field(
        name=f"🎭 Role ({len(roles)})",
        value=", ".join(roles) if roles else "ไม่มี",
        inline=False,
    )

    if member.is_timed_out():
        until = member.timed_out_until.strftime("%d/%m/%Y %H:%M UTC") if member.timed_out_until else "ไม่ทราบ"
        embed.add_field(name="🔇 สถานะ", value=f"ถูกปิดเสียงอยู่ (ถึง {until})", inline=False)
    else:
        embed.add_field(name="🔊 สถานะ", value="ปกติ", inline=False)

    if warns:
        recent = warns[-3:][::-1]  # 3 รายการล่าสุด ใหม่สุดก่อน
        warn_lines = []
        for w in recent:
            date_str = w["timestamp"][:10]
            warn_lines.append(f"• `{date_str}` โดย {w['moderator_name']}: {w['reason']}")
        warn_value = "\n".join(warn_lines)
        if len(warns) > 3:
            warn_value += f"\n*(และอีก {len(warns) - 3} รายการก่อนหน้า)*"
        embed.add_field(
            name=f"⚠️ ประวัติ Warn (รวม {len(warns)} ครั้ง)",
            value=warn_value,
            inline=False,
        )
    else:
        embed.add_field(name="⚠️ ประวัติ Warn", value="ไม่มีประวัติ warn", inline=False)

    await ctx.send(embed=embed)


@userinfo.error
async def userinfo_error(ctx, error):
    if isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ หาสมาชิกคนนี้ไม่เจอ")


# ========== ระบบ Reaction Role ==========

@bot.command(name="reactionrole")
@mod_check("manage_roles")
async def reactionrole(ctx, role: discord.Role, emoji: str, *, label: str):
    """สร้างเมนู Reaction Role ใหม่ พิมพ์ !reactionrole @role อิโมจิ ข้อความอธิบาย"""
    embed = discord.Embed(
        title="🎭 เลือก Role ของคุณ",
        description=f"{emoji} — {label}\n\nกดอิโมจิด้านล่างเพื่อรับ role (เลือกได้แค่ 1 อันในเมนูนี้)",
        color=discord.Color.from_rgb(255, 179, 199),
    )
    message = await ctx.send(embed=embed)
    try:
        await message.add_reaction(emoji)
    except discord.HTTPException:
        await message.delete()
        await ctx.send("❌ อิโมจินี้ใช้ไม่ได้ครับ (พิมพ์ผิด หรือเป็นอิโมจิ custom จากเซิร์ฟอื่นที่บอทเข้าไม่ถึง)")
        return

    data = load_reaction_roles()
    data[str(message.id)] = {
        "channel_id": ctx.channel.id,
        "roles": {emoji: role.id},
        "labels": {emoji: label},
    }
    save_reaction_roles(data)
    await ctx.send(
        f"✅ สร้าง Reaction Role แล้ว (Message ID: `{message.id}`)\n"
        f"เพิ่ม role อื่นในเมนูเดียวกันได้ด้วย: `!reactionrole-add {message.id} @role อิโมจิ ข้อความ`"
    )


@reactionrole.error
async def reactionrole_error(ctx, error):
    if isinstance(error, (commands.MissingPermissions, commands.CheckFailure)):
        await ctx.send("❌ คำสั่งนี้ต้องมีสิทธิ์ Manage Roles หรือ role Bot Admin")
    elif isinstance(error, commands.RoleNotFound):
        await ctx.send("❌ หา role นี้ไม่เจอ")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ ใช้แบบนี้: `!reactionrole @role อิโมจิ ข้อความอธิบาย`")


@bot.command(name="reactionrole-add")
@mod_check("manage_roles")
async def reactionrole_add(ctx, message_id: int, role: discord.Role, emoji: str, *, label: str):
    """เพิ่ม role เข้าไปในเมนู Reaction Role ที่มีอยู่แล้ว พิมพ์ !reactionrole-add <message_id> @role อิโมจิ ข้อความ"""
    data = load_reaction_roles()
    conf = data.get(str(message_id))
    if not conf:
        await ctx.send("❌ ไม่พบเมนู Reaction Role ที่ message_id นี้ (ต้องสร้างด้วย `!reactionrole` ก่อน)")
        return

    channel = ctx.guild.get_channel(conf["channel_id"])
    if channel is None:
        await ctx.send("❌ หาช่องของเมนูนี้ไม่เจอ")
        return
    try:
        message = await channel.fetch_message(message_id)
    except (discord.NotFound, discord.Forbidden):
        await ctx.send("❌ หาข้อความนี้ไม่เจอ (อาจถูกลบไปแล้ว)")
        return

    try:
        await message.add_reaction(emoji)
    except discord.HTTPException:
        await ctx.send("❌ อิโมจินี้ใช้ไม่ได้ครับ")
        return

    conf["roles"][emoji] = role.id
    conf.setdefault("labels", {})[emoji] = label
    save_reaction_roles(data)

    lines = [f"{e} — {l}" for e, l in conf["labels"].items()]
    embed = discord.Embed(
        title="🎭 เลือก Role ของคุณ",
        description="\n".join(lines) + "\n\nกดอิโมจิด้านล่างเพื่อรับ role (เลือกได้แค่ 1 อันในเมนูนี้)",
        color=discord.Color.from_rgb(255, 179, 199),
    )
    await message.edit(embed=embed)
    await ctx.send(f"✅ เพิ่ม {emoji} → {role.mention} เข้าไปในเมนูแล้ว")


@reactionrole_add.error
async def reactionrole_add_error(ctx, error):
    if isinstance(error, (commands.MissingPermissions, commands.CheckFailure)):
        await ctx.send("❌ คำสั่งนี้ต้องมีสิทธิ์ Manage Roles หรือ role Bot Admin")
    elif isinstance(error, commands.RoleNotFound):
        await ctx.send("❌ หา role นี้ไม่เจอ")
    elif isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
        await ctx.send("❌ ใช้แบบนี้: `!reactionrole-add <message_id> @role อิโมจิ ข้อความ`")


# ========== ระบบ Poll ==========

@bot.command(name="poll")
@mod_check("manage_messages")
async def poll(ctx, question: str, *options: str):
    """สร้างโพล พิมพ์ !poll "คำถาม" ตัวเลือก1 ตัวเลือก2 ... (2-9 ตัวเลือก แต่ละตัวเลือกห้ามมีช่องว่าง)"""
    if len(options) < 2:
        await ctx.send('❌ ต้องมีอย่างน้อย 2 ตัวเลือก เช่น `!poll "กินอะไรดี" ข้าว ก๋วยเตี๋ยว`')
        return
    if len(options) > 9:
        await ctx.send("❌ ใส่ตัวเลือกได้สูงสุด 9 อัน")
        return

    emojis = NUMBER_EMOJIS[:len(options)]
    description = "\n".join(f"{emojis[i]} {opt}" for i, opt in enumerate(options))
    embed = discord.Embed(
        title=f"📊 {question}",
        description=description,
        color=discord.Color.from_rgb(255, 179, 199),
    )
    embed.set_footer(text=f"เปิดโดย {ctx.author} • ดูคะแนนสดได้จากอิโมจิ • แอดมินปิดโพลด้วย !endpoll")
    message = await ctx.send(embed=embed)
    for e in emojis:
        await message.add_reaction(e)

    data = load_polls()
    data[str(message.id)] = {
        "channel_id": ctx.channel.id,
        "question": question,
        "options": list(options),
        "emojis": emojis,
        "closed": False,
    }
    save_polls(data)


@poll.error
async def poll_error(ctx, error):
    if isinstance(error, (commands.MissingPermissions, commands.CheckFailure)):
        await ctx.send("❌ คำสั่งนี้ต้องมีสิทธิ์ Manage Messages หรือ role Bot Admin")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send('❌ ใช้แบบนี้: `!poll "คำถาม" ตัวเลือก1 ตัวเลือก2 ...`')


@bot.command(name="endpoll")
@mod_check("manage_messages")
async def endpoll(ctx, message_id: int):
    """ปิดโพลและประกาศผล พิมพ์ !endpoll <message_id>"""
    data = load_polls()
    conf = data.get(str(message_id))
    if not conf:
        await ctx.send("❌ ไม่พบโพลที่ message_id นี้")
        return
    if conf["closed"]:
        await ctx.send("⚠️ โพลนี้ปิดไปแล้ว")
        return

    channel = ctx.guild.get_channel(conf["channel_id"])
    if channel is None:
        await ctx.send("❌ หาช่องของโพลนี้ไม่เจอ")
        return
    try:
        message = await channel.fetch_message(message_id)
    except (discord.NotFound, discord.Forbidden):
        await ctx.send("❌ หาข้อความโพลนี้ไม่เจอ (อาจถูกลบไปแล้ว)")
        return

    results = []
    for emoji, option in zip(conf["emojis"], conf["options"]):
        reaction = discord.utils.get(message.reactions, emoji=emoji)
        count = (reaction.count - 1) if reaction else 0  # หัก 1 เพราะบอทกดเองตอนสร้างโพล
        results.append((option, count))
    results.sort(key=lambda x: x[1], reverse=True)

    top_score = results[0][1]
    lines = []
    for opt, count in results:
        marker = "🏆" if count == top_score and top_score > 0 else "▫️"
        lines.append(f"{marker} **{opt}** — {count} โหวต")

    result_embed = discord.Embed(
        title=f"📊 ผลโพล: {conf['question']} (ปิดแล้ว)",
        description="\n".join(lines),
        color=discord.Color.dark_grey(),
    )
    await ctx.send(embed=result_embed)

    conf["closed"] = True
    save_polls(data)
    try:
        await message.clear_reactions()
    except discord.Forbidden:
        pass


@endpoll.error
async def endpoll_error(ctx, error):
    if isinstance(error, (commands.MissingPermissions, commands.CheckFailure)):
        await ctx.send("❌ คำสั่งนี้ต้องมีสิทธิ์ Manage Messages หรือ role Bot Admin")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ message_id ต้องเป็นตัวเลข ลองก็อปจากการคลิกขวาที่ข้อความ > Copy Message ID")


# ========== ระบบจัดการสิทธิ์แอดมิน ==========

@bot.command(name="setlog")
@mod_check("manage_guild")
async def setlog(ctx):
    """ตั้งค่าช่องที่พิมพ์คำสั่งนี้ให้เป็นช่อง log ของเซิร์ฟเวอร์นี้ พิมพ์ !setlog ในช่องที่ต้องการ"""
    try:
        set_log_channel_id(ctx.guild.id, ctx.channel.id)
    except Exception as e:
        print(f"❌ [setlog] เซฟ config ไม่สำเร็จ: {e}")
        await ctx.send(f"❌ ตั้งค่าไม่สำเร็จ เกิดข้อผิดพลาดตอนเซฟไฟล์: `{e}`\n"
                        f"(เช็คว่า CONFIG_DIR ที่ตั้งไว้ใน Railway Variables ถูกต้อง และ mount path ของ Volume ตรงกันไหม)")
        return
    await ctx.send(f"✅ ตั้งค่าช่องนี้ ({ctx.channel.mention}) เป็นช่อง log ของเซิร์ฟเวอร์นี้แล้วครับ")


@setlog.error
async def setlog_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้ (ต้องมีสิทธิ์ Manage Server หรือ role Bot Admin)")
    else:
        print(f"❌ [setlog] error ที่ไม่คาดคิด: {error}")
        await ctx.send(f"❌ เกิดข้อผิดพลาด: `{error}`")


@bot.command(name="addadmin")
async def addadmin(ctx, member: discord.Member):
    """แต่งตั้งให้คนอื่นใช้คำสั่ง moderation ได้ (เฉพาะเจ้าของเซิร์ฟเวอร์) พิมพ์ !addadmin @ชื่อ"""
    if ctx.author.id != ctx.guild.owner_id:
        await ctx.send("❌ คำสั่งนี้ใช้ได้เฉพาะเจ้าของเซิร์ฟเวอร์เท่านั้น")
        return

    role = await get_or_create_role(ctx.guild, BOT_ADMIN_ROLE_NAME, discord.Color.gold())
    if role in member.roles:
        await ctx.send(f"{member.mention} มีสิทธิ์ Bot Admin อยู่แล้วครับ")
        return

    await member.add_roles(role, reason=f"แต่งตั้งโดยเจ้าของเซิร์ฟเวอร์ ({ctx.author})")
    await ctx.send(f"✅ แต่งตั้ง {member.mention} เป็น **Bot Admin** แล้ว ตอนนี้สามารถใช้คำสั่ง moderation ได้ (kick, ban, mute, warn, clear ฯลฯ)")

    embed = discord.Embed(
        title="👑 แต่งตั้ง Bot Admin",
        description=f"{member.mention} ({member}) ได้รับสิทธิ์ Bot Admin",
        color=discord.Color.gold(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.add_field(name="โดยใคร", value=ctx.author.mention, inline=True)
    await send_log(ctx.guild, embed)


@addadmin.error
async def addadmin_error(ctx, error):
    if isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ หาสมาชิกคนนี้ไม่เจอ")


@bot.command(name="removeadmin")
async def removeadmin(ctx, member: discord.Member):
    """ถอดสิทธิ์ Bot Admin ออกจากคนที่เคยแต่งตั้ง (เฉพาะเจ้าของเซิร์ฟเวอร์) พิมพ์ !removeadmin @ชื่อ"""
    if ctx.author.id != ctx.guild.owner_id:
        await ctx.send("❌ คำสั่งนี้ใช้ได้เฉพาะเจ้าของเซิร์ฟเวอร์เท่านั้น")
        return

    role = discord.utils.get(ctx.guild.roles, name=BOT_ADMIN_ROLE_NAME)
    if role is None or role not in member.roles:
        await ctx.send(f"{member.mention} ไม่มีสิทธิ์ Bot Admin อยู่แล้วครับ")
        return

    await member.remove_roles(role, reason=f"ถอดสิทธิ์โดยเจ้าของเซิร์ฟเวอร์ ({ctx.author})")
    await ctx.send(f"✅ ถอดสิทธิ์ Bot Admin ของ {member.mention} แล้ว")

    embed = discord.Embed(
        title="👑 ถอดสิทธิ์ Bot Admin",
        description=f"{member.mention} ({member}) ถูกถอดสิทธิ์ Bot Admin",
        color=discord.Color.dark_gold(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.add_field(name="โดยใคร", value=ctx.author.mention, inline=True)
    await send_log(ctx.guild, embed)


@removeadmin.error
async def removeadmin_error(ctx, error):
    if isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ หาสมาชิกคนนี้ไม่เจอ")


# ========== คู่มือการใช้งาน ==========

def build_help_embed(guild_name=None):
    """สร้าง embed คู่มือการใช้งานบอททั้งหมด ใช้ทั้งใน !ช่วยด้วย และ DM ตอนบอทเข้าเซิร์ฟเวอร์ใหม่"""
    title = "📖 คู่มือการใช้งานบอท sunday.V2"
    if guild_name:
        title += f" — {guild_name}"
    embed = discord.Embed(title=title, color=discord.Color.from_rgb(255, 179, 199))

    embed.add_field(
        name="🍓 คำสั่งพื้นฐาน",
        value=(
            "`!ping` — เช็คว่าบอทตอบสนองไหม\n"
            "`!hello` — ทักทายบอท\n"
            "`!say <ข้อความ>` — ให้บอทพูดตาม\n"
            "`!info` — ดูข้อมูลเซิร์ฟเวอร์\n"
            "`!ช่วยด้วย` — เปิดคู่มือนี้"
        ),
        inline=False,
    )
    embed.add_field(
        name="✅ ระบบยืนยันตัวตน",
        value="`!verify` — ยืนยันตัวตนเพื่อปลด role Unverified และเข้าใช้งานช่องแชททั้งหมด",
        inline=False,
    )
    embed.add_field(
        name="🛡️ คำสั่ง Moderation (ต้องมีสิทธิ์ หรือ role Bot Admin)",
        value=(
            "`!kick @คน [เหตุผล]` — เตะออกจากเซิร์ฟเวอร์\n"
            "`!ban @คน [เหตุผล]` — แบน\n"
            "`!unban <ชื่อ/ID>` — ปลดแบน\n"
            "`!mute @คน [นาที] [เหตุผล]` — ปิดเสียงชั่วคราว\n"
            "`!unmute @คน` — ยกเลิกปิดเสียง\n"
            "`!warn @คน [เหตุผล]` — เตือน (ครบ 3 auto-mute, ครบ 5 auto-kick)\n"
            "`!clearwarnings @คน` — ล้างประวัติ warn (เฉพาะเจ้าของ/Bot Admin)\n"
            "`!clear <จำนวน>` — ลบข้อความ"
        ),
        inline=False,
    )
    embed.add_field(
        name="🔍 ดูข้อมูลสมาชิก (ใครก็ใช้ได้)",
        value="`!userinfo [@คน]` — ดูโปรไฟล์ + role + สถานะ mute + ประวัติ warn (ไม่ใส่ @คน = ดูตัวเอง)",
        inline=False,
    )
    embed.add_field(
        name="🎭 Reaction Role (ต้องมีสิทธิ์ Manage Roles หรือ role Bot Admin)",
        value=(
            "`!reactionrole @role อิโมจิ ข้อความ` — สร้างเมนู Reaction Role ใหม่\n"
            "`!reactionrole-add <message_id> @role อิโมจิ ข้อความ` — เพิ่ม role เข้าเมนูเดิม\n"
            "*(สมาชิกเลือก role ได้แค่ 1 อันต่อเมนู)*"
        ),
        inline=False,
    )
    embed.add_field(
        name="📊 Poll (ต้องมีสิทธิ์ Manage Messages หรือ role Bot Admin)",
        value=(
            '`!poll "คำถาม" ตัวเลือก1 ตัวเลือก2 ...` — สร้างโพล (สูงสุด 9 ตัวเลือก)\n'
            "`!endpoll <message_id>` — ปิดโพลและประกาศผล"
        ),
        inline=False,
    )
    embed.add_field(
        name="👑 จัดการสิทธิ์แอดมิน (เฉพาะเจ้าของเซิร์ฟเวอร์)",
        value=(
            "`!addadmin @คน` — แต่งตั้งให้ใช้คำสั่ง moderation ได้\n"
            "`!removeadmin @คน` — ถอดสิทธิ์ออก"
        ),
        inline=False,
    )
    embed.add_field(
        name="⚙️ ตั้งค่าเซิร์ฟเวอร์ (ต้องมีสิทธิ์ Manage Server หรือ role Bot Admin)",
        value=(
            "`!setlog` — ตั้งช่องที่พิมพ์คำสั่งนี้ให้เป็นช่อง log ของเซิร์ฟเวอร์นี้ (**ต้องตั้งก่อน ไม่งั้นระบบ log จะไม่ทำงาน**)\n"
            "*Log ครอบคลุม: เข้า-ออกเซิร์ฟ (+เชิญโดยใคร), ข้อความถูกลบ/แก้ไข, VC, ส่งรูป, เปลี่ยนชื่อเล่น/Role/avatar, "
            "สร้าง-ลบช่อง/Role, Pin ข้อความ, Boost เซิร์ฟ, สร้างลิงก์เชิญ, และคำสั่ง moderation ทั้งหมด*"
        ),
        inline=False,
    )
    embed.add_field(
        name="🐛 แจ้งปัญหาบอท (ใครก็ใช้ได้)",
        value="`!report <รายละเอียดปัญหา>` — ส่งข้อความแจ้งปัญหา/บั๊กไปหาผู้พัฒนาโดยตรง",
        inline=False,
    )
    embed.set_footer(text=f"คำนำหน้าคำสั่งทั้งหมดคือ ! (เครื่องหมายตกใจ)  •  พัฒนาโดย {DEVELOPER_CREDIT}")
    return embed


@bot.command(name="ช่วยด้วย")
async def help_th(ctx):
    """แสดงคู่มือการใช้งานบอททั้งหมด พิมพ์ !ช่วยด้วย"""
    embed = build_help_embed(guild_name=ctx.guild.name if ctx.guild else None)
    await ctx.send(embed=embed)


@bot.command(name="report")
async def report(ctx, *, message: str = None):
    """แจ้งปัญหา/บั๊กของบอทไปหาผู้พัฒนาโดยตรง พิมพ์ !report <รายละเอียดปัญหา>"""
    if not message:
        await ctx.send("❌ กรุณาพิมพ์รายละเอียดปัญหาด้วยค่ะ เช่น `!report คำสั่ง !mute ใช้ไม่ได้`")
        return

    dev_owner_id = getattr(bot, "dev_owner_id", None)
    if not dev_owner_id:
        await ctx.send("❌ ตอนนี้ส่งรายงานไม่ได้ (บอทหาผู้พัฒนาไม่เจอ) ลองใหม่ภายหลังนะคะ")
        return

    try:
        developer = await bot.fetch_user(dev_owner_id)
    except discord.NotFound:
        await ctx.send("❌ ตอนนี้ส่งรายงานไม่ได้ ลองใหม่ภายหลังนะคะ")
        return

    embed = discord.Embed(
        title="🐛 มีรายงานปัญหาบอทเข้ามาใหม่",
        description=message,
        color=discord.Color.red(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.add_field(name="👤 ผู้แจ้ง", value=f"{ctx.author} (ID: {ctx.author.id})", inline=False)
    embed.add_field(
        name="🏠 เซิร์ฟเวอร์",
        value=f"{ctx.guild.name} (ID: {ctx.guild.id})" if ctx.guild else "DM",
        inline=False,
    )
    embed.add_field(name="📍 ช่อง", value=ctx.channel.mention if ctx.guild else "DM", inline=False)

    try:
        await developer.send(embed=embed)
        await ctx.send("✅ ส่งรายงานปัญหาไปหาผู้พัฒนาแล้วค่ะ ขอบคุณที่ช่วยแจ้งนะคะ 💗")
    except discord.Forbidden:
        await ctx.send("❌ ส่งรายงานไม่ได้ (ผู้พัฒนาอาจปิดรับ DM) รบกวนแจ้งช่องทางอื่นแทนนะคะ")


# ========== ระบบ Log ขั้นสูง: ช่อง / Role / Pin / โปรไฟล์ ==========

async def get_audit_log_actor(guild, action, target_id=None, within_seconds=10):
    """พยายามหาว่าใครเป็นคนทำ action นี้ล่าสุดจาก Audit Log
    คืนค่า None ถ้าหาไม่เจอ หรือบอทไม่มีสิทธิ์ View Audit Log"""
    try:
        async for entry in guild.audit_logs(action=action, limit=5):
            age = (datetime.datetime.now(datetime.timezone.utc) - entry.created_at).total_seconds()
            if age > within_seconds:
                break
            if target_id is not None and getattr(entry.target, "id", None) != target_id:
                continue
            return entry.user
    except discord.Forbidden:
        return None
    return None


@bot.event
async def on_guild_channel_create(channel):
    """บันทึก log เมื่อมีการสร้างช่องใหม่"""
    guild = channel.guild
    actor = await get_audit_log_actor(guild, discord.AuditLogAction.channel_create, target_id=channel.id)
    embed = discord.Embed(
        title="📁 สร้างช่องใหม่",
        color=discord.Color.green(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.add_field(name="ช่อง", value=getattr(channel, "mention", f"#{channel.name}"), inline=True)
    embed.add_field(name="ประเภท", value=str(channel.type), inline=True)
    embed.add_field(name="โดยใคร", value=str(actor) if actor else "ไม่ทราบ", inline=True)
    await send_log(guild, embed)


@bot.event
async def on_guild_channel_delete(channel):
    """บันทึก log เมื่อมีการลบช่อง"""
    guild = channel.guild
    actor = await get_audit_log_actor(guild, discord.AuditLogAction.channel_delete)
    embed = discord.Embed(
        title="🗑️ ลบช่อง",
        color=discord.Color.red(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.add_field(name="ชื่อช่อง", value=f"#{channel.name}", inline=True)
    embed.add_field(name="ประเภท", value=str(channel.type), inline=True)
    embed.add_field(name="โดยใคร", value=str(actor) if actor else "ไม่ทราบ", inline=True)
    await send_log(guild, embed)


@bot.event
async def on_guild_role_create(role):
    """บันทึก log เมื่อมีการสร้าง role ใหม่ในเซิร์ฟเวอร์"""
    actor = await get_audit_log_actor(role.guild, discord.AuditLogAction.role_create, target_id=role.id)
    embed = discord.Embed(
        title="🎭 สร้าง Role ใหม่",
        color=discord.Color.green(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.add_field(name="Role", value=role.mention, inline=True)
    embed.add_field(name="โดยใคร", value=str(actor) if actor else "ไม่ทราบ", inline=True)
    await send_log(role.guild, embed)


@bot.event
async def on_guild_role_delete(role):
    """บันทึก log เมื่อมีการลบ role ในเซิร์ฟเวอร์"""
    actor = await get_audit_log_actor(role.guild, discord.AuditLogAction.role_delete)
    embed = discord.Embed(
        title="🗑️ ลบ Role",
        color=discord.Color.red(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.add_field(name="ชื่อ Role", value=role.name, inline=True)
    embed.add_field(name="โดยใคร", value=str(actor) if actor else "ไม่ทราบ", inline=True)
    await send_log(role.guild, embed)


@bot.event
async def on_guild_channel_pins_update(channel, last_pin):
    """บันทึก log เมื่อมีการ pin/unpin ข้อความ (ใช้ Audit Log หาว่าใครทำและข้อความไหน)"""
    guild = getattr(channel, "guild", None)
    if guild is None:
        return

    matched_entry = None
    try:
        async for entry in guild.audit_logs(limit=5):
            if entry.action not in (discord.AuditLogAction.message_pin, discord.AuditLogAction.message_unpin):
                continue
            age = (datetime.datetime.now(datetime.timezone.utc) - entry.created_at).total_seconds()
            if age > 10:
                break
            matched_entry = entry
            break
    except discord.Forbidden:
        return

    if matched_entry is None:
        return  # หาไม่เจอจาก audit log ก็ข้ามไป กันข้อความ log ที่ไม่มีข้อมูลเป็นประโยชน์

    is_pin = matched_entry.action == discord.AuditLogAction.message_pin
    embed = discord.Embed(
        title="📌 Pin ข้อความ" if is_pin else "📌 Unpin ข้อความ",
        color=discord.Color.gold() if is_pin else discord.Color.light_grey(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.add_field(name="ช่อง", value=channel.mention, inline=True)
    embed.add_field(name="โดยใคร", value=str(matched_entry.user) if matched_entry.user else "ไม่ทราบ", inline=True)
    message_id = getattr(matched_entry.extra, "message_id", None)
    if message_id:
        embed.add_field(name="Message ID", value=str(message_id), inline=True)
    await send_log(guild, embed)


@bot.event
async def on_user_update(before, after):
    """บันทึก log เมื่อสมาชิกเปลี่ยน username หรือ avatar (แจ้งในทุกเซิร์ฟที่บอทเจอคนนี้อยู่ด้วย)"""
    changes = []
    if before.name != after.name:
        changes.append(f"Username: `{before.name}` → `{after.name}`")
    if before.avatar != after.avatar:
        changes.append("เปลี่ยนรูปโปรไฟล์ (avatar)")

    if not changes:
        return

    for guild in bot.guilds:
        member = guild.get_member(after.id)
        if member is None:
            continue
        embed = discord.Embed(
            title="👤 เปลี่ยนข้อมูลโปรไฟล์",
            description=f"{after.mention} ({after})",
            color=discord.Color.blurple(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.add_field(name="การเปลี่ยนแปลง", value="\n".join(changes), inline=False)
        if before.avatar != after.avatar:
            embed.set_thumbnail(url=after.display_avatar.url)
        await send_log(guild, embed)


@bot.event
async def on_guild_join(guild):
    """เมื่อบอทถูกเชิญเข้าเซิร์ฟเวอร์ใหม่: DM หาเจ้าของเซิร์ฟพร้อมคู่มือการใช้งาน"""
    print(f"➕ เข้าร่วมเซิร์ฟเวอร์ใหม่: {guild.name} (เจ้าของ: {guild.owner})")

    owner = guild.owner
    if owner is None:
        try:
            owner = await guild.fetch_member(guild.owner_id)
        except (discord.NotFound, discord.Forbidden):
            owner = None

    if owner is None:
        print(f"⚠️ หาเจ้าของเซิร์ฟเวอร์ '{guild.name}' ไม่เจอ ส่ง DM ไม่ได้")
        return

    embed = build_help_embed(guild_name=guild.name)
    try:
        await owner.send(
            content=f"👋 สวัสดีค่ะ! บอท **sunday.V2** เข้าร่วมเซิร์ฟเวอร์ **{guild.name}** ของคุณเรียบร้อยแล้ว "
                    f"นี่คือคู่มือการใช้งานทั้งหมดค่ะ 💗\n\n"
                    f"⚠️ **อย่าลืมตั้งค่าช่อง log ก่อนใช้งาน!** ไปที่ช่องที่ต้องการให้เป็น log แล้วพิมพ์ `!setlog` "
                    f"ไม่งั้นระบบบันทึก log จะยังไม่ทำงานนะคะ",
            embed=embed,
        )
    except discord.Forbidden:
        print(f"⚠️ ส่ง DM หาเจ้าของเซิร์ฟเวอร์ '{guild.name}' ไม่ได้ (เขาอาจปิดรับ DM จากคนที่ไม่รู้จัก)")


@bot.event
async def on_command_error(ctx, error):
    """ดักจับ error ที่ไม่มี error handler เฉพาะของคำสั่งนั้นๆ กันไม่ให้เงียบหายไปเฉยๆ"""
    if isinstance(error, commands.CommandNotFound):
        return  # ไม่ต้องแจ้งถ้าพิมพ์คำสั่งที่ไม่มีอยู่จริง
    if isinstance(error, commands.CheckFailure):
        await ctx.send("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้")
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ ใส่ข้อมูลไม่ครบ ลองพิมพ์ `!ช่วยด้วย` เพื่อดูวิธีใช้คำสั่งนี้")
        return
    print(f"❌ [on_command_error] คำสั่ง '{ctx.command}' เกิดข้อผิดพลาด: {error}")
    await ctx.send(f"❌ เกิดข้อผิดพลาดที่ไม่คาดคิด: `{error}`")


if __name__ == "__main__":
    if not TOKEN:
        print("❌ ไม่พบ DISCORD_TOKEN กรุณาตรวจสอบไฟล์ .env")
    else:
        bot.run(TOKEN)