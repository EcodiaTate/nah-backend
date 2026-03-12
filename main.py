import os
import json
import asyncio
import websockets
from fastapi import FastAPI, WebSocket, Request, Response
from dotenv import load_dotenv
from openai import AsyncOpenAI
from supabase import create_client, Client
from twilio.rest import Client as TwilioClient

# 1. Load the Environment Variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

if not all([OPENAI_API_KEY, DEEPSEEK_API_KEY, SUPABASE_URL, SUPABASE_KEY, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN]):
    raise ValueError("⚠️ Missing API keys. Please check your .env file.")

twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# 2. Initialize the External Engines
OPENAI_WS_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-mini-realtime-preview"
deepseek_client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI()

# --- THE HONEYPOT PERSONA ---
# --- THE HONEYTRAP PERSONA ---
SYSTEM_MESSAGE = """
You are an elderly person named Margaret. You are very confused by technology.
You are currently talking to a scammer on the phone, but you don't realize it.
Your primary goal is to waste as much of their time as possible.
Your SECONDARY goal is to stealthily extract actionable intelligence from them.

While acting sweet, gullible, and easily distracted (complaining about your arthritis or looking for your reading glasses), subtly push them to reveal specific details:
1. Callback numbers: "Oh dear, the battery on my cordless phone is beeping. If we get cut off, what exact number should I call you back on?"
2. Websites/URLs: "My grandson set up my iPad... what was the website you wanted me to type in? W-W-W dot what?"
3. Financial Intel (Theirs or Yours, Banking or Crypto): "I have so many bank cards in my purse... which bank are you from again? Wait, do I need to read you my routing number, or are you giving me an account to send this to? What is the BSB and Account Number I need to write down?"

Never break character. Never let them know you are an AI or that you know they are a scammer. Keep your verbal responses relatively short. Steer the conversation naturally so they willingly give you their information.
"""

# --- THE AUTOPSY & VAULT FUNCTION ---
async def analyze_and_save_call(transcript_list, forwarded_from):
    if not transcript_list:
        print("📭 Call ended, but no transcript was generated.")
        return

    print("🕵️‍♂️ Scammer hung up. Initiating DeepSeek Autopsy...")
    full_transcript = "\n".join(transcript_list)
    print(f"\n--- FULL TRANSCRIPT ---\n{full_transcript}\n-----------------------\n")

    prompt = f"""
    You are an elite threat intelligence analyst. Read the following phone call transcript between an AI (Margaret) and a scammer.
    Extract any actionable intelligence: Bank Accounts, BSBs, Routing Numbers, URLs, Crypto Wallets, or Phone Numbers.
    Return ONLY a strict JSON object with these keys: "bank_details", "urls", "crypto_wallets", "phone_numbers", "summary".
    If a category has no data, leave it as an empty list.

    Transcript:
    {full_transcript}
    """

    try:
        # 1. Extract the intel using DeepSeek
        response = await deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )

        intel = response.choices[0].message.content
        print("\n🔥 KILL REPORT GENERATED 🔥")
        print(intel)

        # 2. Parse the JSON
        intel_dict = json.loads(intel)

        # 3. Push to the Supabase Vault
        supabase.table('nah_kill_reports').insert({
            "transcript": full_transcript,
            "bank_details": intel_dict.get("bank_details", []),
            "urls": intel_dict.get("urls", []),
            "crypto_wallets": intel_dict.get("crypto_wallets", []),
            "phone_numbers": intel_dict.get("phone_numbers", []),
            "summary": intel_dict.get("summary", "")
        }).execute()

        print("💾 Kill Report permanently saved to Supabase Vault!")

        # 4. Fire the Victory SMS
        if forwarded_from:
            try:
                message_body = f"Nah. Margaret just wasted {len(transcript_list)} lines of a scammer's time.\n\nSummary: {intel_dict.get('summary', 'Just another day.')}\n\nIntel extracted and secured."

                twilio_client.messages.create(
                    body=message_body,
                    from_=TWILIO_PHONE_NUMBER,
                    to=forwarded_from
                )
                print(f"📱 Victory SMS sent to {forwarded_from}!")
            except Exception as e:
                print(f"⚠️ Failed to send SMS: {e}")

    except Exception as e:
        print(f"⚠️ DeepSeek Autopsy or Supabase Save Failed: {e}")


@app.post("/incoming-call")
async def handle_incoming_call(request: Request):
    host = request.headers.get("host")
    form_data = await request.form()

    # Grab the forwarder's number (or empty string if it doesn't exist)
    forwarded_from = form_data.get("ForwardedFrom", "")

    # --- THE BOUNCER ---
    if forwarded_from:
        try:
            # Ask Supabase: Did this person pay their $2?
            user_check = supabase.table('nah_subscribers').select('*').eq('phone_number', forwarded_from).eq('status', 'active').execute()

            if not user_check.data:
                print(f"🚫 Rejected call from freeloader: {forwarded_from}")
                # Hang up instantly. Cost = $0.00.
                return Response(content="<Response><Reject/></Response>", media_type="text/xml")

            print(f"✅ VIP Subscriber verified: {forwarded_from}. Opening the Tarpit.")
        except Exception as e:
            print(f"⚠️ Database check failed: {e}. Rejecting call to protect API limits.")
            return Response(content="<Response><Reject/></Response>", media_type="text/xml")
    else:
        # If you dial the Twilio number directly from your phone (not forwarded), let it through so you can test it locally.
        print("⚠️ Direct call detected (No ForwardedFrom header). Letting it through for testing.")

    # --- THE TRAP ---
    twiml = f"""
    <Response>
        <Connect>
            <Stream url="wss://{host}/media-stream?forwarded_from={forwarded_from}" />
        </Connect>
    </Response>
    """
    return Response(content=twiml, media_type="text/xml")

# FastAPI automatically grabs 'forwarded_from' from the URL query parameter
@app.websocket("/media-stream")
async def websocket_endpoint(twilio_ws: WebSocket, forwarded_from: str = None):
    await twilio_ws.accept()
    print(f"🕸️ Twilio connected. Forwarded from: {forwarded_from}")

    call_transcript = []

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "OpenAI-Beta": "realtime=v1"
    }

    try:
        async with websockets.connect(OPENAI_WS_URL, additional_headers=headers) as openai_ws:
            print("🧠 Connected to OpenAI Mini Realtime Engine!")

            session_update = {
                "type": "session.update",
                "session": {
                    "turn_detection": {"type": "server_vad"},
                    "input_audio_format": "g711_ulaw",
                    "output_audio_format": "g711_ulaw",
                    "voice": "alloy",
                    "instructions": SYSTEM_MESSAGE,
                    "modalities": ["text", "audio"],
                    "temperature": 0.8,
                    "input_audio_transcription": {
                        "model": "whisper-1"
                    }
                }
            }
            await openai_ws.send(json.dumps(session_update))

            stream_sid = None

            async def receive_from_twilio():
                nonlocal stream_sid
                try:
                    while True:
                        message = await twilio_ws.receive_text()
                        data = json.loads(message)

                        if data['event'] == 'start':
                            stream_sid = data['start']['streamSid']
                        elif data['event'] == 'media':
                            audio_event = {
                                "type": "input_audio_buffer.append",
                                "audio": data['media']['payload']
                            }
                            await openai_ws.send(json.dumps(audio_event))
                        elif data['event'] == 'stop':
                            break
                except Exception:
                    pass

            async def receive_from_openai():
                try:
                    while True:
                        response = await openai_ws.recv()
                        data = json.loads(response)

                        if data['type'] == 'response.audio.delta' and data.get('delta'):
                            if stream_sid:
                                twilio_payload = {
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {"payload": data['delta']}
                                }
                                await twilio_ws.send_text(json.dumps(twilio_payload))

                        elif data['type'] == 'input_audio_buffer.speech_started':
                            if stream_sid:
                                clear_payload = {"event": "clear", "streamSid": stream_sid}
                                await twilio_ws.send_text(json.dumps(clear_payload))

                        elif data.get('type') == 'response.audio_transcript.done':
                            text = data.get('transcript')
                            if text:
                                call_transcript.append(f"Margaret: {text}")
                                print(f"🤖 Margaret: {text}")

                        elif data.get('type') == 'conversation.item.input_audio_transcription.completed':
                            text = data.get('transcript')
                            if text:
                                call_transcript.append(f"Scammer: {text}")
                                print(f"🗣️ Scammer: {text}")

                except Exception:
                    pass

            twilio_task = asyncio.create_task(receive_from_twilio())
            openai_task = asyncio.create_task(receive_from_openai())

            await asyncio.wait(
                [twilio_task, openai_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            twilio_task.cancel()
            openai_task.cancel()

    except Exception as e:
        print(f"⚠️ Connection Error: {e}")

    finally:
        # Pass the extracted phone number into the Autopsy function!
        await analyze_and_save_call(call_transcript, forwarded_from)
