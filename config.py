from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    base_url: str = "https://your-domain.ngrok.io"

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_currency: str = "brl"

    # Menu
    menu_path: str = "menu.json"

    # Impressora de Comanda (ESC/POS)
    printer_type: str = "dummy"
    printer_host: str = "192.168.1.100"
    printer_port: int = 9100
    printer_usb_vendor: str = "0x04b8"
    printer_usb_product: str = "0x0202"
    printer_serial_port: str = "/dev/ttyUSB0"
    printer_serial_baud: int = 9600

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
