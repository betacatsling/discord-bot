import os
import importlib.metadata as _metadata  # noqa: WPS436

# Work around Python 3.9 stdlib missing packages_distributions (needed by google-generativeai)
try:
    _ = _metadata.packages_distributions
except AttributeError:
    try:
        import importlib_metadata as _importlib_metadata  # type: ignore

        _metadata.packages_distributions = _importlib_metadata.packages_distributions  # type: ignore[attr-defined]
    except Exception:
        pass

import asyncio

import discord
import google.generativeai as genai
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# 1. 加载环境变量
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_NAME = "gemini-1.5-flash"
GUILD_ID = os.getenv("GUILD_ID")  # 可选：指定单个测试服务器以加速 Slash 命令同步
PROXY_URL = os.getenv("PROXY_URL", "http://127.0.0.1:7897")

# 让 Discord 和 Gemini 请求都走本地代理（支持 HTTP/SOCKS，例如 socks5h://127.0.0.1:7897）
if PROXY_URL:
    os.environ.setdefault("HTTP_PROXY", PROXY_URL)
    os.environ.setdefault("HTTPS_PROXY", PROXY_URL)
    os.environ.setdefault("ALL_PROXY", PROXY_URL)

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# 2. 配置 Intents (意图)
# 必须开启 message_content 才能读取用户发送的消息文本
intents = discord.Intents.default()
intents.message_content = True

# 3. 实例化 Bot 对象
# command_prefix 用于旧式的文本命令 (如 !ping)，但在 Slash Command 中不是必须的
bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    proxy=PROXY_URL if PROXY_URL else None,  # 代理所有请求到本地端口（支持 SOCKS）
)


# --- 事件监听 ---
@bot.event
async def on_ready():
    """当机器人连接成功时触发"""
    print(f"已登录为 {bot.user} (ID: {bot.user.id})")

    # 同步 Slash Commands 到 Discord 服务器
    # 注意：在生产环境中，频繁同步可能会被限流，建议指定 guild (服务器) 同步用于测试
    try:
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            # 将全局命令复制到指定服务器以便快速出现
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(
                f"已同步到测试服务器 {GUILD_ID} 的 {len(synced)} 个命令"
                "（若为 0 表示命令已存在且无变更）"
            )
        else:
            synced = await bot.tree.sync()
            print(f"已同步 {len(synced)} 个命令（全局同步可能需几分钟才能在客户端出现）")
    except Exception as e:
        print(f"同步命令失败: {e}")


@bot.event
async def on_message(message):
    """监听所有消息"""
    # 避免机器人回复自己
    if message.author == bot.user:
        return

    # 简单的关键词回复
    if message.content.lower() == "hello":
        await message.channel.send(f"你好, {message.author.mention}!")

    # 处理命令（如果混合使用旧式命令，必须加这行）
    await bot.process_commands(message)


# --- 定义 Slash Commands (推荐方式) ---
@bot.tree.command(name="ping", description="检查机器人的延迟")
async def ping(interaction: discord.Interaction):
    """输入 /ping 返回延迟"""
    # interaction 是用户交互的上下文
    latency = round(bot.latency * 1000)  # 转换为毫秒
    # 使用 response.send_message 回复，ephemeral=True 表示只有用户自己能看到
    await interaction.response.send_message(f"Pong! 延迟为 {latency}ms", ephemeral=False)


@bot.tree.command(name="add", description="计算两个数的和")
@app_commands.describe(a="第一个数字", b="第二个数字")
async def add(interaction: discord.Interaction, a: int, b: int):
    """输入 /add a:1 b:2"""
    result = a + b
    await interaction.response.send_message(f"{a} + {b} = {result}")


@bot.tree.command(name="gemini", description="向 Gemini 提问")
@app_commands.describe(prompt="想问的问题或指令")
async def gemini(interaction: discord.Interaction, prompt: str):
    """输入 /gemini prompt:你的问题"""
    if not GEMINI_API_KEY:
        await interaction.response.send_message(
            "Gemini API key 未配置，请在 .env 设置 GEMINI_API_KEY 后重启机器人。",
            ephemeral=True,
        )
        return

    await interaction.response.defer(thinking=True)
    loop = asyncio.get_running_loop()

    def _call_gemini() -> str:
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        result = model.generate_content(prompt)
        return result.text or "（Gemini 没有返回文本内容）"

    try:
        content = await asyncio.wait_for(
            loop.run_in_executor(None, _call_gemini),
            timeout=30,
        )
    except asyncio.TimeoutError:
        await interaction.followup.send(
            "Gemini 请求超时，请稍后再试或缩短提示。",
            ephemeral=True,
        )
        return
    except Exception as exc:  # noqa: BLE001
        await interaction.followup.send(
            f"调用 Gemini 失败：{exc}", ephemeral=True
        )
        return

    # 限制消息长度以避免超出 Discord 限制
    if len(content) > 1800:
        content = content[:1800] + "…"
    await interaction.followup.send(content)


# 4. 启动机器人
if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("错误：未找到 DISCORD_TOKEN，请检查 .env 文件")
