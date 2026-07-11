"""
บอท Discord พื้นฐาน - ตัวอย่างเริ่มต้น
ใช้ไลบรารี discord.py

วิธีใช้:
1. ติดตั้งไลบรารี: pip install discord.py python-dotenv
2. สร้างไฟล์ .env แล้วใส่ DISCORD_TOKEN=โทเคนของคุณ
3. รันไฟล์นี้: python bot.py
"""

import os
import datetime
import discord
from discord.ext import commands
from dotenv import load_dotenv

# โหลดค่าจากไฟล์ .env (เก็บ Token แยกจากโค้ด เพื่อความปลอดภัย)
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))

UNVERIFIED_ROLE_NAME = "Unverified"
VERIFIED_ROLE_NAME = "Verified"
BOT_ADMIN_ROLE_NAME = "Bot Admin"  # role ที่เจ้าของเซิร์ฟใช้แต่งตั้งให้คนอื่นใช้คำสั่ง moderation ได้

# ตั้งค่า Intents (สิทธิ์การเข้าถึงข้อมูลต่างๆ)
intents = discord.Intents.default()
intents.message_content = True  # จำเป็นถ้าต้องการให้บอทอ่านเนื้อหาข้อความ
intents.members = True  # จำเป็นสำหรับ on_member_join/on_member_remove (ต้องไปเปิด "SERVER MEMBERS INTENT" ใน Discord Developer Portal ด้วย)

# สร้างบอท โดยใช้ "!" เป็นคำนำหน้าคำสั่ง (เปลี่ยนได้ตามต้องการ)
bot = commands.Bot(command_prefix="!", intents=intents)


async def send_log(guild, embed):
    """ส่ง embed ไปที่ช่อง log ถ้าตั้งค่า LOG_CHANNEL_ID ไว้"""
    if not LOG_CHANNEL_ID:
        print("⚠️ [LOG] ไม่ได้ตั้งค่า LOG_CHANNEL_ID ใน .env (ค่าเป็น 0 หรือว่าง)")
        return
    channel = guild.get_channel(LOG_CHANNEL_ID)
    if channel is None:
        # เผื่อ cache ยังไม่มีช่องนี้ ลอง fetch จาก API โดยตรง
        try:
            channel = await guild.fetch_channel(LOG_CHANNEL_ID)
        except discord.NotFound:
            print(f"❌ [LOG] ไม่พบช่อง ID {LOG_CHANNEL_ID} ในเซิร์ฟเวอร์ '{guild.name}' "
                  f"(เช็คว่า ID ถูกต้องไหม หรือ copy ID ช่องผิดจากเซิร์ฟเวอร์อื่น)")
            return
        except discord.Forbidden:
            print(f"❌ [LOG] บอทไม่มีสิทธิ์เข้าถึงช่อง ID {LOG_CHANNEL_ID}")
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

    # เช็ค log channel ทันทีตอนสตาร์ท จะได้รู้ปัญหาไว้ก่อน ไม่ต้องรอ event เกิดขึ้นจริง
    if not LOG_CHANNEL_ID:
        print("⚠️ [เช็ค LOG_CHANNEL_ID] ไม่พบค่าใน .env หรือค่าเป็น 0 — log จะไม่ทำงานเลย!")
    else:
        found_in_any_guild = False
        for guild in bot.guilds:
            channel = guild.get_channel(LOG_CHANNEL_ID)
            if channel:
                print(f"✅ [เช็ค LOG_CHANNEL_ID] เจอช่อง log: '#{channel.name}' ในเซิร์ฟเวอร์ '{guild.name}'")
                found_in_any_guild = True
        if not found_in_any_guild:
            print(f"❌ [เช็ค LOG_CHANNEL_ID] ID {LOG_CHANNEL_ID} ไม่ตรงกับช่องใดๆ ในเซิร์ฟเวอร์ที่บอทอยู่ "
                  f"— เช็คว่า copy ID ช่องมาถูกไหม (คลิกขวาที่ช่อง > Copy Channel ID, ต้องเปิด Developer Mode ก่อน)")


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

    # บันทึก log
    embed = discord.Embed(
        title="📥 สมาชิกใหม่เข้าเซิร์ฟเวอร์",
        description=f"{member.mention} ({member})",
        color=discord.Color.green(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
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
    embed.add_field(name="เนื้อหา", value=message.content or "(ไม่มีข้อความ/เป็นรูปภาพ)", inline=False)
    await send_log(message.guild, embed)


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
    """เตือนสมาชิก พิมพ์ !warn @ชื่อ เหตุผล"""
    dm_sent = await send_dm_template(
        member,
        title="⚠️ คุณถูกเตือน",
        description=f"คุณถูกเตือนในเซิร์ฟเวอร์ **{ctx.guild.name}**",
        extra_fields=[("🍓 เหตุผล", reason)],
    )
    dm_status = "(ส่ง DM แจ้งแล้ว)" if dm_sent else "(ส่ง DM ไม่ได้ อาจปิดรับข้อความส่วนตัว)"
    await ctx.send(f"⚠️ เตือน {member.mention} แล้ว {dm_status}\nเหตุผล: {reason}")


@warn.error
async def warn_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้ (ต้องมีสิทธิ์ Kick Members หรือ role Bot Admin)")


# ========== ระบบจัดการสิทธิ์แอดมิน ==========

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
            "`!warn @คน [เหตุผล]` — เตือน\n"
            "`!clear <จำนวน>` — ลบข้อความ"
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
    embed.set_footer(text="คำนำหน้าคำสั่งทั้งหมดคือ ! (เครื่องหมายตกใจ)")
    return embed


@bot.command(name="ช่วยด้วย")
async def help_th(ctx):
    """แสดงคู่มือการใช้งานบอททั้งหมด พิมพ์ !ช่วยด้วย"""
    embed = build_help_embed(guild_name=ctx.guild.name if ctx.guild else None)
    await ctx.send(embed=embed)


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
                    f"นี่คือคู่มือการใช้งานทั้งหมดค่ะ 💗",
            embed=embed,
        )
    except discord.Forbidden:
        print(f"⚠️ ส่ง DM หาเจ้าของเซิร์ฟเวอร์ '{guild.name}' ไม่ได้ (เขาอาจปิดรับ DM จากคนที่ไม่รู้จัก)")


if __name__ == "__main__":
    if not TOKEN:
        print("❌ ไม่พบ DISCORD_TOKEN กรุณาตรวจสอบไฟล์ .env")
    else:
        bot.run(TOKEN)