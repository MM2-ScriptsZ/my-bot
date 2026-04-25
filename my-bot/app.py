import discord
from discord import app_commands
from discord.ext import commands
import httpx
import random
import asyncio
from datetime import datetime
import os

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Roblox API endpoints
USERS_API = "https://users.roblox.com/v1/users/authenticated"
AUTH_API = "https://auth.roblox.com/"
BIRTHDATE_API = "https://accountinformation.roblox.com/v1/birthdate"
ACCOUNT_SETTINGS_API = "https://accountsettings.roblox.com/v1/account/settings"

# User agents for spoofing
USER_AGENTS = [
    "Roblox/WinInet (RobloxApp/0.546.0.5460326)",
    "RobloxStudio/WinInet (RobloxStudio/0.546.0.5460326)",
    "com.roblox.client/1.0 (Android 13; Pixel 6)",
    "Roblox/1.0 (iPhone; iOS 16.0; iPhone13,2)",
]

def generate_random_birthdate():
    """Generate random birthdate making account under 13"""
    current_year = datetime.now().year
    random_year = current_year - random.randint(5, 12)
    random_month = random.randint(1, 12)
    
    if random_month == 2:
        max_day = 28
    elif random_month in [4, 6, 9, 11]:
        max_day = 30
    else:
        max_day = 31
    
    random_day = random.randint(1, max_day)
    
    return {
        "iso": f"{random_year}-{random_month:02d}-{random_day:02d}",
        "formatted": f"{random_month:02d}/{random_day:02d}/{random_year}",
        "day": random_day,
        "month": random_month,
        "year": random_year
    }

async def get_csrf_token(cookie, user_agent=None):
    """Fetch CSRF token from Roblox"""
    try:
        headers = {"Cookie": f".ROBLOSECURITY={cookie}"}
        if user_agent:
            headers["User-Agent"] = user_agent
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(AUTH_API, headers=headers)
            if resp.status_code == 403:
                return resp.headers.get("x-csrf-token")
    except Exception:
        pass
    return None

async def verify_and_get_user(cookie):
    """Validate Roblox cookie and return user info"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                USERS_API,
                headers={"Cookie": f".ROBLOSECURITY={cookie}"}
            )
            
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "success": True,
                    "username": data.get("name", "Unknown"),
                    "user_id": data.get("id", 0),
                    "age_verified": data.get("isVerified", False)
                }
    except Exception:
        pass
    
    return {"success": False, "error": "Invalid or expired cookie"}

# METHOD 1: Official Roblox API
async def method1_official_api(cookie, birthdate_iso):
    csrf = await get_csrf_token(cookie)
    if not csrf:
        return {"success": False, "error": "Failed to get CSRF token"}
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                BIRTHDATE_API,
                json={"birthDate": birthdate_iso},
                headers={
                    "Cookie": f".ROBLOSECURITY={cookie}",
                    "x-csrf-token": csrf,
                    "Content-Type": "application/json"
                }
            )
            
            if resp.status_code == 200:
                return {"success": True, "method": "Official API"}
            else:
                return {"success": False, "method": "Official API", "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"success": False, "method": "Official API", "error": str(e)}

# METHOD 2: Account Settings Endpoint
async def method2_account_settings(cookie, birthdate_info):
    csrf = await get_csrf_token(cookie)
    if not csrf:
        return {"success": False}
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            payload = {
                "birthDay": birthdate_info["day"],
                "birthMonth": birthdate_info["month"],
                "birthYear": birthdate_info["year"]
            }
            
            resp = await client.post(
                ACCOUNT_SETTINGS_API,
                json=payload,
                headers={
                    "Cookie": f".ROBLOSECURITY={cookie}",
                    "x-csrf-token": csrf,
                    "Content-Type": "application/json"
                }
            )
            
            if resp.status_code == 200:
                return {"success": True, "method": "Account Settings"}
            else:
                return {"success": False, "method": "Account Settings", "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"success": False, "method": "Account Settings", "error": str(e)}

# METHOD 3: Spoofed Headers + Mobile User-Agent
async def method3_spoofed_headers(cookie, birthdate_iso):
    for user_agent in USER_AGENTS:
        try:
            csrf = await get_csrf_token(cookie, user_agent)
            if not csrf:
                continue
            
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    BIRTHDATE_API,
                    json={"birthDate": birthdate_iso},
                    headers={
                        "Cookie": f".ROBLOSECURITY={cookie}",
                        "x-csrf-token": csrf,
                        "Content-Type": "application/json",
                        "User-Agent": user_agent,
                        "Accept": "application/json"
                    }
                )
                
                if resp.status_code == 200:
                    return {"success": True, "method": f"Spoofed Headers"}
        except Exception:
            continue
    
    return {"success": False, "method": "Spoofed Headers", "error": "All user-agents failed"}

# METHOD 4: CSRF Token Rotation + Delayed Retry
async def method4_csrf_rotation(cookie, birthdate_iso):
    for attempt in range(3):
        try:
            csrf = await get_csrf_token(cookie)
            if not csrf:
                await asyncio.sleep(1)
                continue
            
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    BIRTHDATE_API,
                    json={"birthDate": birthdate_iso},
                    headers={
                        "Cookie": f".ROBLOSECURITY={cookie}",
                        "x-csrf-token": csrf,
                        "Content-Type": "application/json"
                    }
                )
                
                if resp.status_code == 200:
                    return {"success": True, "method": f"CSRF Rotation"}
                
                if resp.status_code == 403:
                    new_csrf = resp.headers.get("x-csrf-token")
                    if new_csrf:
                        await asyncio.sleep(2)
                        retry_resp = await client.post(
                            BIRTHDATE_API,
                            json={"birthDate": birthdate_iso},
                            headers={
                                "Cookie": f".ROBLOSECURITY={cookie}",
                                "x-csrf-token": new_csrf,
                                "Content-Type": "application/json"
                            }
                        )
                        
                        if retry_resp.status_code == 200:
                            return {"success": True, "method": f"CSRF Rotation"}
        except Exception:
            continue
        
        await asyncio.sleep(1)
    
    return {"success": False, "method": "CSRF Rotation", "error": "All rotation attempts failed"}

# MASTER BYPASS FUNCTION - All 4 Methods
async def master_bypass(cookie, birthdate_info):
    """Try all 4 bypass methods in sequence"""
    
    # Method 1: Official API
    m1 = await method1_official_api(cookie, birthdate_info["iso"])
    if m1["success"]:
        return {"success": True, "method_used": m1["method"], "birthdate": birthdate_info["formatted"]}
    
    await asyncio.sleep(1)
    
    # Method 2: Account Settings
    m2 = await method2_account_settings(cookie, birthdate_info)
    if m2["success"]:
        return {"success": True, "method_used": m2["method"], "birthdate": birthdate_info["formatted"]}
    
    await asyncio.sleep(1)
    
    # Method 3: Spoofed Headers
    m3 = await method3_spoofed_headers(cookie, birthdate_info["iso"])
    if m3["success"]:
        return {"success": True, "method_used": m3["method"], "birthdate": birthdate_info["formatted"]}
    
    await asyncio.sleep(1)
    
    # Method 4: CSRF Rotation
    m4 = await method4_csrf_rotation(cookie, birthdate_info["iso"])
    if m4["success"]:
        return {"success": True, "method_used": m4["method"], "birthdate": birthdate_info["formatted"]}
    
    # All methods failed
    return {"success": False, "birthdate": birthdate_info["formatted"]}

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    print(f"✅ Bot is ready with 4 bypass methods")
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"❌ Sync error: {e}")

@bot.tree.command(
    name="bypass", 
    description="Auto-verify + age bypass (4 methods)"
)
@app_commands.describe(cookie="Your Roblox .ROBLOSECURITY cookie")
async def bypass(interaction: discord.Interaction, cookie: str):
    """Single command: verify cookie and attempt all 4 bypass methods"""
    
    await interaction.response.defer()
    
    # Send initial status
    await interaction.followup.send("🔍 **Step 1/3:** Verifying your Roblox cookie...")
    
    # Verify cookie
    verify_result = await verify_and_get_user(cookie)
    
    if not verify_result["success"]:
        embed = discord.Embed(
            title="❌ Auto-Verify Failed",
            description="The Roblox cookie is **invalid or expired**.\n\n"
                       "📌 **How to get a valid cookie:**\n"
                       "1. Log into Roblox in your browser\n"
                       "2. Press F12 → Application → Cookies\n"
                       "3. Copy the value of `.ROBLOSECURITY`\n\n"
                       "⚠️ Never share your cookie with anyone!",
            color=discord.Color.red()
        )
        await interaction.edit_original_response(content=None, embed=embed)
        return
    
    # Generate random birthdate
    await interaction.edit_original_response(
        content=f"✅ **Step 1/3:** Cookie verified! (User: `{verify_result['username']}`)\n"
               f"🔄 **Step 2/3:** Generating random birthdate..."
    )
    
    birthdate = generate_random_birthdate()
    
    await interaction.edit_original_response(
        content=f"✅ **Step 1/3:** Cookie verified! (User: `{verify_result['username']}`)\n"
               f"✅ **Step 2/3:** Random birthdate: `{birthdate['formatted']}`\n"
               f"🔄 **Step 3/3:** Trying 4 bypass methods in sequence..."
    )
    
    # Attempt all 4 methods
    bypass_result = await master_bypass(cookie, birthdate)
    
    # Create final embed
    if bypass_result["success"]:
        embed = discord.Embed(
            title="✅ AGE BYPASS SUCCESSFUL!",
            description=f"**Working Method:** {bypass_result['method_used']}",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="👤 Roblox Account",
            value=f"**Username:** `{verify_result['username']}`\n"
                  f"**User ID:** `{verify_result['user_id']}`\n"
                  f"**Age Verified:** {'✅ Yes' if verify_result.get('age_verified') else '❌ No'}",
            inline=False
        )
        
        embed.add_field(
            name="🎲 NEW BIRTHDATE",
            value=f"**{bypass_result['birthdate']}**\n\n"
                  f"Account is now **under 13**",
            inline=False
        )
        
    else:
        embed = discord.Embed(
            title="❌ AGE BYPASS FAILED",
            description=f"**All 4 methods failed**\n\n"
                       f"Attempted birthdate: **{bypass_result['birthdate']}**",
            color=discord.Color.red()
        )
        
        embed.add_field(
            name="👤 Roblox Account",
            value=f"**Username:** `{verify_result['username']}`\n"
                  f"**User ID:** `{verify_result['user_id']}`\n"
                  f"**Age Verified:** {'✅ Yes' if verify_result.get('age_verified') else '❌ No'}",
            inline=False
        )
        
        embed.add_field(
            name="📋 Methods Tried",
            value="• Official API\n"
                  "• Account Settings\n"
                  "• Spoofed Headers\n"
                  "• CSRF Rotation",
            inline=False
        )
    
    embed.set_footer(
        text="⚠️ 4-method bypass mode | For educational purposes only",
        icon_url="https://cdn.discordapp.com/embed/avatars/0.png"
    )
    
    await interaction.edit_original_response(content=None, embed=embed)

@bot.tree.command(name="ping", description="Check bot status")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(
        f"🏓 Pong! Latency: {latency}ms\n"
        f"✅ 4-method bypass bot online"
    )

@bot.tree.command(name="methods", description="List all bypass methods")
async def methods(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🔧 Available Bypass Methods",
        description="The bot tries these 4 methods in order",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="📌 Method 1", value="**Official API**\nDirect birthdate endpoint", inline=False)
    embed.add_field(name="📌 Method 2", value="**Account Settings**\nAlternative settings endpoint", inline=False)
    embed.add_field(name="📌 Method 3", value="**Spoofed Headers**\nMobile/app user-agent spoofing", inline=False)
    embed.add_field(name="📌 Method 4", value="**CSRF Rotation**\nToken rotation + delayed retry", inline=False)
    
    await interaction.response.send_message(embed=embed)

# Run the bot
if __name__ == "__main__":
    token = os.environ.get("BOT_TOKEN")
    if not token:
        print("❌ BOT_TOKEN environment variable not set!")
        print("💡 Make sure you have a .env file with BOT_TOKEN=your_token")
    else:
        print("🚀 Starting 4-METHOD age bypasser bot...")
        print("=" * 50)
        bot.run(token)
