"""
Order Ticket Printer — ESC/POS
Supports thermal printers via:
  - Network TCP/IP (most common in restaurants)
  - USB
  - Serial

Compatible: Epson TM-T20, and any generic ESC/POS printer.
"""
import asyncio
import logging
from datetime import datetime
from config import get_settings
from session import CallSession

logger = logging.getLogger(__name__)
settings = get_settings()


def _center(text: str, width: int = 42) -> str:
    return text.center(width)


def _divider(char: str = "-", width: int = 42) -> str:
    return char * width


def build_comanda_text(session: CallSession) -> list[dict]:
    from menu import get_restaurant_info
    restaurant = get_restaurant_info()
    now = datetime.now()
    commands = []

    def add(type_, value=None):
        commands.append({"type": type_, "value": value})

    add("align", "center")
    add("bold_on")
    add("text", restaurant["name"].upper())
    add("bold_off")
    add("text", "")
    add("text", _center("═══ COMANDA ═══"))
    add("text", "")

    add("align", "left")
    add("bold_on")
    add("text", "Pedido N°:")
    add("bold_off")
    add("text", f"  #{session.order_id}")
    add("text", "")
    add("text", f"Data/Hora: {now.strftime('%d/%m/%Y %H:%M:%S')}")
    add("text", f"Telefone:     {session.from_number}")
    add("text", "")
    add("text", _divider())

    add("bold_on")
    add("text", "ITENS DO PEDIDO:")
    add("bold_off")
    add("text", "")

    for item in session.order_items:
        qty_name = f"  {item.quantity}x {item.name}"
        price = f"R$ {item.total:.2f}"
        spaces = 42 - len(qty_name) - len(price)
        line = qty_name + (" " * max(1, spaces)) + price
        add("text", line)

    add("text", "")
    add("text", _divider())

    total_label = "TOTAL:"
    total_value = f"R$ {session.order_total:.2f}"
    spaces = 42 - len(total_label) - len(total_value)
    add("bold_on")
    add("text", total_label + (" " * max(1, spaces)) + total_value)
    add("bold_off")

    add("text", "")
    add("text", _divider())
    add("align", "center")
    add("bold_on")
    add("text", "✓ PAGO")
    add("bold_off")
    add("text", "")

    prep = restaurant.get("prep_time_minutes", 20)
    add("text", f"Pronto em aprox. {prep} minutes")
    add("text", "Retire no balcão")
    add("text", "")
    add("text", _divider("═"))
    add("text", _center("Obrigado!"))
    add("text", _divider("═"))
    add("text", "")
    add("text", "")
    add("feed", 4)
    add("cut")

    return commands


async def print_comanda(session: CallSession) -> bool:
    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None, _print_sync, session
        )
        return result
    except Exception as e:
        logger.error(f"[Printer] Failed to print comanda for order {session.order_id}: {e}")
        return False


def _print_sync(session: CallSession) -> bool:
    try:
        from escpos.printer import Network, Usb, Serial, Dummy
    except ImportError:
        logger.error("[Printer] python-escpos not installed.")
        return False

    printer_type = settings.printer_type.lower()
    commands = build_comanda_text(session)

    try:
        if printer_type == "network":
            p = Network(settings.printer_host, port=settings.printer_port, timeout=5)
        elif printer_type == "usb":
            p = Usb(
                idVendor=int(settings.printer_usb_vendor, 16),
                idProduct=int(settings.printer_usb_product, 16),
            )
        elif printer_type == "serial":
            p = Serial(devfile=settings.printer_serial_port, baudrate=settings.printer_serial_baud)
        elif printer_type == "dummy":
            p = Dummy()
        else:
            logger.error(f"[Printer] Unknown printer type: {printer_type}")
            return False

        for cmd in commands:
            ctype = cmd["type"]
            value = cmd.get("value")
            if ctype == "text":
                p.text((value or "") + "\n")
            elif ctype == "bold_on":
                p.set(bold=True)
            elif ctype == "bold_off":
                p.set(bold=False)
            elif ctype == "align":
                p.set(align=value)
            elif ctype == "feed":
                p.ln(value or 1)
            elif ctype == "cut":
                p.cut()

        if printer_type == "dummy":
            logger.info(f"[Printer DUMMY] Output:\n{p.output.decode('cp850', errors='replace')}")

        logger.info(f"[Printer] ✅ Order #{session.order_id} printed via {printer_type}")
        return True

    except Exception as e:
        logger.error(f"[Printer] ❌ Print error: {e}")
        return False
