#!/usr/bin/env python3
"""ZYGOR v4.1 Telegram Bot – Self-re-trigger, never stops"""
import os, logging, asyncio, json, time, hashlib, re
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, CommandHandler, ContextTypes, InlineQueryHandler, MessageHandler, filters

# === CONFIG ===
TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
ALLOWED = [CHAT_ID] if CHAT_ID else []
WATERMARK = " @zygorlap"
AI_MODEL = os.environ.get('AI_MODEL', '')
SESSION_TOKEN = os.environ.get('SESSION_TOKEN', '')
TARGET = os.environ.get('TARGET', '127.0.0.1')
PHASE = os.environ.get('PHASE', 'full')
REPO = os.environ.get('GITHUB_REPO', '')
RUN_ID = os.environ.get('GITHUB_RUN_ID', '')
WORKFLOW_ID = os.environ.get('WORKFLOW_ID', '')
MAX_HOURS = int(os.environ.get('MAX_HOURS', '6'))
START_TIME = time.time()
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
LHOST = os.environ.get('LHOST', '')
LPORT = os.environ.get('LPORT', '4444')
ENABLE_EXFIL = os.environ.get('ENABLE_EXFIL', 'false')
CTF_MODE = os.environ.get('CTF_MODE', 'false')

logging.basicConfig(filename='/var/log/zygor/telegram_bot.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def authorised(update):
    return not ALLOWED or str(update.effective_chat.id) in ALLOWED

async def ai_query(prompt: str) -> str:
    """Query Ollama directly via HTTP"""
    model = AI_MODEL
    if not model or model in ('none', 'null'):
        try:
            proc = await asyncio.create_subprocess_exec(
                'curl', '-s', '--max-time', '5', 'http://localhost:11434/api/tags',
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            data = json.loads(out.decode())
            if data.get('models'):
                model = data['models'][0]['name']
        except:
            model = 'mistral:7b-instruct-q4_K_M'

    for attempt in range(3):
        try:
            proc = await asyncio.create_subprocess_exec(
                'curl', '-s', '-X', 'POST', 'http://localhost:11434/api/generate',
                '--connect-timeout', '15', '--max-time', '120',
                '-H', 'Content-Type: application/json',
                '-d', json.dumps({
                    "model": model, "prompt": prompt,
                    "stream": False, "keep_alive": "24h",
                    "options": {"num_predict": 2048, "temperature": 0.3, "repeat_penalty": 1.1, "top_p": 0.9}
                }),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=150)
            resp = stdout.decode()
            if resp:
                data = json.loads(resp)
                if data.get('response'):
                    return data['response'].strip()
                if data.get('error'):
                    return f"ERROR: {data['error']}"
        except asyncio.TimeoutError:
            if attempt < 2:
                await asyncio.sleep(5)
                continue
            return "ERROR: AI query timed out after 150s"
        except Exception as e:
            logging.error(f"AI error: {e}")
            if attempt < 2:
                await asyncio.sleep(5)
                continue
            return f"ERROR: {str(e)[:300]}"
    return "ERROR: All attempts failed"

async def self_re_trigger():
    """Wait until near max duration, then dispatch new workflow"""
    delay = max(60, (MAX_HOURS * 3600) - 1800)   # 30 min before end
    logging.info(f"Re-trigger waiting {delay}s")
    await asyncio.sleep(delay)

    if not GITHUB_TOKEN:
        logging.error("No GITHUB_TOKEN – cannot re-trigger")
        return

    payload = json.dumps({
        "ref": "main",
        "inputs": {
            "target": TARGET,
            "lhost": LHOST,
            "lport": LPORT,
            "ai_model": AI_MODEL,
            "penetration_phase": PHASE,
            "enable_exfiltration": ENABLE_EXFIL,
            "run_duration_hours": str(MAX_HOURS),
            "telegram_enable": "true",
            "telegram_chat_id": CHAT_ID,
            "telegram_bot_token": TOKEN,
            "session_token": SESSION_TOKEN
        }
    })

    url = f'https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW_ID}/dispatches'
    for attempt in range(5):
        try:
            proc = await asyncio.create_subprocess_exec(
                'curl', '-s', '-X', 'POST', url,
                '-H', f'Authorization: token {GITHUB_TOKEN}',
                '-H', 'Accept: application/vnd.github.v3+json',
                '-d', payload,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            out, err = await asyncio.wait_for(proc.communicate(), timeout=30)
            resp = out.decode()
            logging.info(f"Re-trigger attempt {attempt+1}: {resp[:200]}")
            if proc.returncode == 0:
                # Signal success to parent process
                with open('/tmp/re_trigger_done', 'w') as f:
                    f.write('ok')
                return
        except Exception as e:
            logging.error(f"Re-trigger failed: {e}")
            await asyncio.sleep(30)

    logging.error("All re-trigger attempts exhausted")

# ======== Command handlers (same as before, shortened for brevity) =========
async def cmd_start(u, c):
    if not authorised(u): return
    elapsed = int((time.time() - START_TIME) / 60)
    await u.message.reply_text(f"🔥 ZYGOR v4.1 🎯 {TARGET}\n🧠 {AI_MODEL}\n⏱ {elapsed}m")

async def cmd_help(u, c):
    if not authorised(u): return
    await u.message.reply_text(
        "/start /help /ai <q> /exec <cmd> /scan <t> /recon <d> /exploit <v> "
        "/webforge <desc> /crackhash <h> /cve <id> /phish <t> /ctf <ch> "
        "/reverse <f> /poly <lh> <lp> /c2 <lh> <lp> /persist /lateral /pivot "
        "/stego /wireless /report /log /abort /watermark /clear /session /regen"
    )

async def cmd_ai(u, c):
    if not authorised(u): return
    q = ' '.join(c.args)
    if not q: await u.message.reply_text("/ai <question>"); return
    await u.message.reply_text("🧠 Thinking...")
    r = await ai_query(q)
    await u.message.reply_text(r[:4000])

async def cmd_exec(u, c):
    if not authorised(u): return
    cmd = ' '.join(c.args)
    if not cmd: await u.message.reply_text("/exec <command>"); return
    try:
        proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
        await u.message.reply_text((out.decode()[:3500]) or "No output")
    except asyncio.TimeoutError:
        await u.message.reply_text("Command timed out")

async def cmd_scan(u, c):
    if not authorised(u): return
    t = c.args[0] if c.args else TARGET
    await u.message.reply_text(f"🔍 Scanning {t}...")
    proc = await asyncio.create_subprocess_shell(f"nmap -sV -sC -T4 --min-rate=2000 -p- {t} 2>&1 | tail -30",
                                                 stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    o, _ = await asyncio.wait_for(proc.communicate(), timeout=300)
    res = o.decode()[:2000]
    ai = await ai_query(f"Analyze these nmap results for vulnerabilities: {res[:1500]}")
    await u.message.reply_text(res + "\n---\n🤖 " + ai[:2000])

# ... (include all other handlers from your original script: exploit, shellcode, payload,
# evade, scanadv, subdomain, dirbust, sqli, xss, lfi, ssrf, rce, privesc, pcap,
# hashdump, dnsscan, smbcheck, webcheck, cloudenum, reverse, webforge, crackhash,
# cve, phish, ctf, poly, c2, persist, lateral, pivot, stego, wireless, report,
# log, abort, watermark, clear, session, regen) 
# For brevity I'm not copying them all, but **you must include them** in your file.
# They are identical to your existing handlers.

async def handle_document(u, c):
    if not authorised(u): return
    doc = u.message.document
    f = await c.bot.get_file(doc.file_id)
    fp = f"/tmp/{doc.file_name}"
    await f.download_to_drive(fp)
    await u.message.reply_text(f"📁 Saved: {fp}")

async def inline_query(u, c):
    q = u.inline_query.query
    if not q: return
    r = await ai_query(q)
    results = [InlineQueryResultArticle(
        id=hashlib.md5(q.encode()).hexdigest(),
        title="ZYGOR AI",
        input_message_content=InputTextMessageContent(r[:4000])
    )]
    await u.inline_query.answer(results)

def main():
    app = Application.builder().token(TOKEN).build()
    # Add all command handlers (use the full list from your original)
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("ai", cmd_ai))
    app.add_handler(CommandHandler("exec", cmd_exec))
    app.add_handler(CommandHandler("scan", cmd_scan))
    # ... add all others

    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(InlineQueryHandler(inline_query))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(self_re_trigger())
    app.run_polling()

if __name__ == '__main__':
    main()
