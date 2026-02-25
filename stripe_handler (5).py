"""
Stripe payment handler — PT-BR.
"""
import stripe
import asyncio
import logging
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response
from config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/payment", tags=["payment"])
settings = get_settings()

stripe.api_key = settings.stripe_secret_key


async def create_payment_link(session) -> tuple[str, str]:
    line_items = []
    for item in session.order_items:
        line_items.append({
            "price_data": {
                "currency": settings.stripe_currency,
                "product_data": {"name": item.name},
                "unit_amount": int(item.unit_price * 100),
            },
            "quantity": item.quantity,
        })

    payment_link = stripe.PaymentLink.create(
        line_items=line_items,
        metadata={
            "order_id": session.order_id,
            "call_sid": session.call_sid,
            "customer_phone": session.from_number,
        },
        after_completion={
            "type": "hosted_confirmation",
            "hosted_confirmation": {
                "custom_message": f"Pedido #{session.order_id} confirmado! Retire no balcão."
            },
        },
    )

    return payment_link.url, payment_link.id


async def _send_confirmation_sms(phone: str, order_id: str, total: float):
    """Envia SMS de confirmação mesmo se a ligação cair."""
    try:
        from menu import get_restaurant_info
        from twilio.rest import Client
        restaurant = get_restaurant_info()
        address = restaurant.get("address", "nosso restaurante")
        prep_time = restaurant.get("prep_time_minutes", 15)
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

        message = (
            f"✅ {restaurant['name']}\n"
            f"Pagamento confirmado!\n"
            f"Pedido #{order_id} — R$ {total:.2f}\n\n"
            f"Pronto em aprox. {prep_time} min.\n"
            f"Retire em: {address}"
        )

        client.messages.create(
            body=message,
            from_=settings.twilio_phone_number,
            to=phone,
        )
        logger.info(f"SMS de confirmação enviado para {phone}, pedido {order_id}")
    except Exception as e:
        logger.error(f"Erro ao enviar SMS de confirmação: {e}")


@router.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Assinatura inválida")

    logger.info(f"Stripe event: {event['type']}")

    if event["type"] == "checkout.session.completed":
        stripe_session = event["data"]["object"]
        metadata = stripe_session.get("metadata", {})
        call_sid = metadata.get("call_sid")
        order_id = metadata.get("order_id")
        customer_phone = metadata.get("customer_phone")

        if call_sid:
            from session import get_session
            from comanda import print_comanda
            session = get_session(call_sid)
            if session:
                session.payment_confirmed = True
                total = session.order_total
                logger.info(f"Pagamento confirmado: pedido {order_id}, ligação {call_sid}")
                asyncio.create_task(print_comanda(session))
                asyncio.create_task(_send_confirmation_sms(customer_phone, order_id, total))

    elif event["type"] == "payment_intent.succeeded":
        payment_intent = event["data"]["object"]
        metadata = payment_intent.get("metadata", {})
        call_sid = metadata.get("call_sid")

        if call_sid:
            from session import get_session
            from comanda import print_comanda
            session = get_session(call_sid)
            if session and not session.payment_confirmed:
                session.payment_confirmed = True
                session.payment_intent_id = payment_intent["id"]
                asyncio.create_task(print_comanda(session))

    return Response(status_code=200)
