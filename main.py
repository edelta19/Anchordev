import threading
from flask import Flask, session, redirect, request, url_for, render_template_string, jsonify
import requests
import os
import discord
from discord.ext import commands

# --- CONFIGURATION ---
CLIENT_ID = "1379515377310109706"
CLIENT_SECRET = "umpI0zJRbIUc4EFZuiK8oWOqQIOxnwET"
REDIRECT_URI = "https://your-app-name.onrender.com/callback" # Update this after deploying!
BOT_TOKEN = "MTM3OTUxNTM3NzMxMDEwOTcwNg.GzlvEc.aKpWYxJP06HLNded8ZVCk2N7b-ItgUwiqXsBt0"
API_ENDPOINT = "https://discord.com/api/v10"
SECRET_KEY = os.urandom(24)

# --- SETUP FLASK & BOT ---
app = Flask(__name__)
app.secret_key = SECRET_KEY

# Enable "Message Content Intent" in Developer Portal for this to work
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- FLASK ROUTES (The Website) ---

def exchange_code(code):
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI,
        'scope': 'identify guilds'
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    r = requests.post(f'{API_ENDPOINT}/oauth2/token', data=data, headers=headers)
    return r.json()

def get_user_guilds(access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    r = requests.get(f'{API_ENDPOINT}/users/@me/guilds', headers=headers)
    return r.json() if r.status_code == 200 else []

def is_staff(permissions):
    perm_int = int(permissions)
    return (perm_int & 0x8) == 0x8 or (perm_int & 0x20) == 0x20

@app.route('/')
def index():
    if 'user' in session: return redirect(url_for('dashboard'))
    return f'<a href="/login">Login with Discord</a>'

@app.route('/login')
def login():
    return redirect(f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20guilds")

@app.route('/callback')
def callback():
    code = request.args.get('code')
    token_resp = exchange_code(code)
    if 'access_token' in token_resp:
        session['access_token'] = token_resp['access_token']
        headers = {'Authorization': f"Bearer {session['access_token']}"}
        session['user'] = requests.get(f'{API_ENDPOINT}/users/@me', headers=headers).json()
        return redirect(url_for('dashboard'))
    return "Login Failed"

@app.route('/dashboard')
def dashboard():
    if 'user' not in session: return redirect(url_for('index'))
    guilds = get_user_guilds(session['access_token'])
    staff_guilds = [g for g in guilds if is_staff(g['permissions'])]
    
    # Simple HTML List
    html = "<h1>Select Server</h1>"
    for g in staff_guilds:
        html += f"<div><h3>{g['name']}</h3><a href='/server/{g['id']}'>Manage</a></div>"
    return html

@app.route('/server/<guild_id>')
def manage(guild_id):
    if 'user' not in session: return redirect(url_for('index'))
    return f"""
    <h1>Manage Server {guild_id}</h1>
    <form action="/api/kick" method="post">
        <input name="user_id" placeholder="User ID">
        <input name="guild_id" type="hidden" value="{guild_id}">
        <button type="submit">Kick User</button>
    </form>
    """

@app.route('/api/kick', methods=['POST'])
def api_kick():
    # In a real app, VERIFY PERMISSIONS HERE AGAIN!
    user_id = request.form.get('user_id')
    guild_id = request.form.get('guild_id')
    
    # We use the running BOT to do the kick
    guild = bot.get_guild(int(guild_id))
    if not guild: return "Bot is not in that server!"
    
    # We need to run the async bot function from this sync Flask route
    future = bot.loop.run_until_complete(kick_member(guild, user_id))
    return "User Kicked!"

async def kick_member(guild, user_id):
    member = await guild.fetch_member(int(user_id))
    await member.kick(reason="Kicked via Dashboard")

# --- DISCORD BOT EVENTS ---

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}!")

@bot.command()
async def ping(ctx):
    await ctx.send("Pong! (I am alive and hosting the website)")

# --- RUNNING BOTH ---

def run_flask():
    # Run Flask on port 10000 (standard for Render) or 5000
    app.run(host='0.0.0.0', port=10000)

if __name__ == '__main__':
    # 1. Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    # 2. Start the Bot in the main thread
    bot.run(BOT_TOKEN)
