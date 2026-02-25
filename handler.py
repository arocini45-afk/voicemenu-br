"""
Twilio Voice Webhook Handler — ConversationRelay PT-BR com Duda.
"""
import json
import asyncio
import logging
from fastapi import APIRouter, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from session import create_session, get_session, CallState
from conversation import (
    get_ai_response,
    get_initial_greeting,
    get_payment_confirmation_message,
    get_waiting_for_payment_message,
    process_ai_action,
)
from stripe_handler import create_payment_link
from sms import send_payment_sms
from config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["voice"])
settings = get_settings()


@router.post("/incoming")
async def handle_incoming_call(
    CallSid: str = Form(...),
    From: str = Form(...),
    To: str = Form(...),
):
    logger.info(f"Incoming call: {CallSid} from {From}")
    session = create_session(CallSid, From)
    greeting = await get_initial_greeting(session)

    ws_url = f"{settings.base_url.replace('https://', 'wss://')}/voice/ws"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <ConversationRelay
      url="{ws_url}"
      welcomeGreeting="{greeting['speech']}"
      ttsProvider="ElevenLabs"
      voice="pFZP5JQG7iQjIQuC4Bku"
      language="pt-BR"
      transcriptionProvider="deepgram"
      speechModel="nova-2"
    />
  </Connect>
</Response>"""

    return Response(content=twiml, media_type="application/xml")


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    call_sid = None
    session = None

    try:
        async for message in websocket.iter_text():
            data = json.loads(message)
            event_type = data.get("type")

            if event_type == "setup":
                call_sid = data.get("callSid")
                session = get_session(call_sid)
                logger.info(f"ConversationRelay conectado: {call_sid}")

            elif event_type == "prompt":
                if not session:
                    continue

                transcript = data.get("voicePrompt", "").strip()
                logger.info(f"[{call_sid}] Cliente disse: '{transcript}'")

                if not transcript:
                    continue

                ai_result = await get_ai_response(session, transcript)
                process_ai_action(session, ai_result)

                ai_speech = ai_result.get("speech", "")
                action = ai_result.get("action", "none")
                logger.info(f"[{call_sid}] Duda diz: '{ai_speech}' | action: {action}")

                if action == "send_payment" and not session.payment_link:
                    try:
                        payment_link, payment_intent_id = await create_payment_link(session)
                        session.payment_link = payment_link
                        session.payment_intent_id = payment_intent_id

                        await send_payment_sms(
                            to_number=session.from_number,
                            order_id=session.order_id,
                            payment_link=payment_link,
                            total=session.order_total,
                            language="pt",
                        )

                        session.state = CallState.PAYMENT_SENT
                        waiting_msg = await get_waiting_for_payment_message(session)
                        full_msg = f"{ai_speech} {waiting_msg}"

                        await websocket.send_text(json.dumps({
                            "type": "text",
                            "token": full_msg,
                            "last": True,
                        }))

                        asyncio.create_task(
                            wait_for_payment_and_confirm(websocket, session, call_sid)
                        )
                        continue

                    except Exception as e:
                        logger.error(f"Erro no pagamento: {e}")
                        ai_speech = "Desculpe, houve um problema ao processar o pagamento. Por favor, ligue novamente."

                if action == "end_call":
                    await websocket.send_text(json.dumps({
                        "type": "text",
                        "token": ai_speech,
                        "last": True,
                    }))
                    await asyncio.sleep(3)
                    await websocket.send_text(json.dumps({"type": "end"}))
                    break

                await websocket.send_text(json.dumps({
                    "type": "text",
                    "token": ai_speech,
                    "last": True,
                }))

            elif event_type == "interrupt":
                logger.info(f"[{call_sid}] Cliente interrompeu")

            elif event_type == "error":
                logger.error(f"[{call_sid}] Erro ConversationRelay: {data}")

    except WebSocketDisconnect:
        logger.info(f"WebSocket desconectado: {call_sid}")
    except Exception as e:
        logger.error(f"Erro WebSocket: {e}")


async def wait_for_payment_and_confirm(websocket: WebSocket, session, call_sid: str):
    max_wait = 300
    interval = 5
    elapsed = 0

    while elapsed < max_wait:
        await asyncio.sleep(interval)
        elapsed += interval

        if session.payment_confirmed:
            confirmation_msg = await get_payment_confirmation_message(session)
            try:
                await websocket.send_text(json.dumps({
                    "type": "text",
                    "token": confirmation_msg,
                    "last": True,
                }))
                await asyncio.sleep(5)
                await websocket.send_text(json.dumps({"type": "end"}))
            except Exception as e:
                logger.error(f"Erro ao enviar confirmação: {e}")
            return

    logger.warning(f"Timeout de pagamento para ligação {call_sid}")
