import discord
import os
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

# 1. 加载环境变量
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# 2. 配置 Intents (意图)
# 必须开启 message_content 才能读取用户发送的消息文本
intents = discord.Intents.default()
intents.message_content = True

# 3. 实例化 Bot 对象
# command_prefix 用于旧式的文本命令 (如 !ping)，但在 Slash Command 中不是必须的
bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    proxy="http://127.0.0.1:7897",  # 代理所有请求到本地 7897 端口
)


# --- 事件监听 ---
@bot.event
async def on_ready():
    """当机器人连接成功时触发"""
    print(f"已登录为 {bot.user} (ID: {bot.user.id})")

    # 同步 Slash Commands 到 Discord 服务器
    # 注意：在生产环境中，频繁同步可能会被限流，建议指定 guild (服务器) 同步用于测试
    try:
        synced = await bot.tree.sync()
        print(f"已同步 {len(synced)} 个命令")
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


# 4. 启动机器人
if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("错误：未找到 DISCORD_TOKEN，请检查 .env 文件")
