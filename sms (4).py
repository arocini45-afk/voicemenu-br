"""
SMS handler — envia link de pagamento e confirmação por SMS.
"""
from twilio.rest import Client
from config import get_settings
from menu import get_restaurant_info
import logging

logger = logging.getLogger(__name__)
settings = get_settings()


async def send_payment_sms(
    to_number: str,
    order_id: str,
    payment_link: str,
    total: float,
    language: str = "pt",
):
    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    restaurant = get_restaurant_info()
    restaurant_name = restaurant["name"]

    message_body = (
        f"🍔 {restaurant_name}\n"
        f"Pedido #{order_id}\n"
        f"Total: R$ {total:.2f}\n\n"
        f"Clique para pagar:\n"
        f"{payment_link}\n\n"
        f"Após o pagamento, aguarde a confirmação na ligação."
    )

    message = client.messages.create(
        body=message_body,
        from_=settings.twilio_phone_number,
        to=to_number,
    )

    logger.info(f"SMS enviado para {to_number}, SID: {message.sid}")
    return message.sid
