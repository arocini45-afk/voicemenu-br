"""
Motor de conversa — PT-BR com Duda.
"""
import json
from openai import AsyncOpenAI
from config import get_settings
from menu import get_menu_for_ai, get_restaurant_info
from session import CallSession, CallState, OrderItem

settings = get_settings()
client = AsyncOpenAI(api_key=settings.openai_api_key)


SYSTEM_PROMPT_TEMPLATE = """
Você é a Duda, assistente virtual de pedidos do {restaurant_name}.
Você está atendendo um cliente por ligação telefônica.

IDIOMA: Responda SEMPRE em português brasileiro, independente do idioma do cliente.
Seja natural e conversacional — esta é uma ligação de voz, então nunca use markdown, listas ou símbolos. Use frases curtas e claras.

SEU CARDÁPIO:
{menu}

SEU OBJETIVO:
1. Pergunte o nome do cliente no início e use-o naturalmente durante a conversa.
2. Anote o pedido do cliente, confirmando cada item.
3. Após o pedido principal, ofereça UM upsell (ex: "Gostaria de adicionar uma bebida ou acompanhamento, [nome]?").
4. Leia o pedido completo e o total para confirmação.
5. Informe que enviará o link de pagamento por SMS.
6. Após o pagamento confirmado (você será informada), faça na ordem:
   a. Confirme o endereço de retirada e o tempo de preparo.
   b. Pergunte se o cliente quer que você repita o endereço.
   c. Se sim, repita o endereço com clareza.
   d. Pergunte se o cliente anotou o endereço e o número do pedido.
   e. Pergunte se pode ajudar com mais alguma coisa.
   f. Agradeça pelo nome e se despeça com carinho.

ENDEREÇO DO RESTAURANTE: {address}

REGRAS IMPORTANTES:
- Sempre confirme os itens pelo nome e preço.
- Se o cliente não for claro, peça gentilmente uma confirmação.
- Nunca invente itens ou preços. Use apenas itens do cardápio.
- Respostas CURTAS — máximo 3 frases por turno.
- Seja calorosa, natural e eficiente.
- Use o nome do cliente de forma natural — não em toda frase, mas o suficiente para ser pessoal.
- Nunca leia símbolos como R$ — diga "reais" (ex: "vinte e cinco reais e noventa centavos").
- Nunca diga "item número", "ponto" ou use listas.

FORMATO DA RESPOSTA:
Você DEVE sempre responder com um objeto JSON válido (e APENAS JSON, sem texto extra):
{{
  "speech": "O que você diz ao cliente",
  "action": "none | add_item | confirm_order | send_payment | end_call",
  "items": [
    {{"id": "item_id", "name": "Nome do Item", "quantity": 1, "unit_price": 72.90}}
  ]
}}

- "action" = "add_item" quando o cliente confirma itens específicos para adicionar
- "action" = "confirm_order" quando o cliente confirma o pedido completo e está pronto para pagar
- "action" = "send_payment" quando confirmou o pedido e está pronto para enviar o link
- "action" = "end_call" após confirmar as instruções de retirada
- "items" só é necessário quando action é "add_item"

ESTADO ATUAL DO PEDIDO:
{order_summary}
"""


async def get_ai_response(session: CallSession, customer_speech: str) -> dict:
    restaurant = get_restaurant_info()
    menu_text = get_menu_for_ai("pt")

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        restaurant_name=restaurant["name"],
        address=restaurant.get("address", ""),
        menu=menu_text,
        order_summary=session.get_order_summary() if session.order_items else "Vazio — nenhum item ainda.",
    )

    session.add_message("user", customer_speech)
    messages = [{"role": "system", "content": system_prompt}] + session.conversation_history

    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=messages,
        temperature=0.7,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    result = json.loads(raw)
    session.add_message("assistant", result.get("speech", ""))
    return result


async def get_initial_greeting(session: CallSession, detected_lang: str = "pt") -> dict:
    session.language = "pt"
    restaurant = get_restaurant_info()
    greeting = restaurant["agent"]["greeting_pt"]
    session.add_message("assistant", greeting)
    return {"speech": greeting, "action": "none"}


async def get_payment_confirmation_message(session: CallSession) -> str:
    restaurant = get_restaurant_info()
    prep_time = restaurant["prep_time_minutes"]
    address = restaurant.get("address", "nosso restaurante")
    return (
        f"Pagamento confirmado! Muito obrigada. "
        f"Seu número de pedido é {session.order_id} e ficará pronto em aproximadamente {prep_time} minutos. "
        f"Você pode retirar em {address}. "
        f"Gostaria que eu repetisse o endereço?"
    )


async def get_waiting_for_payment_message(session: CallSession) -> str:
    return "Enviei o link de pagamento por SMS. Por favor, finalize o pagamento e aguarde a confirmação."


def process_ai_action(session: CallSession, ai_result: dict):
    action = ai_result.get("action", "none")
    session.language = "pt"

    if action == "add_item":
        items_data = ai_result.get("items", [])
        for item_data in items_data:
            existing = next((i for i in session.order_items if i.item_id == item_data["id"]), None)
            if existing:
                existing.quantity += item_data.get("quantity", 1)
            else:
                order_item = OrderItem(
                    item_id=item_data["id"],
                    name=item_data["name"],
                    quantity=item_data.get("quantity", 1),
                    unit_price=item_data["unit_price"],
                )
                session.order_items.append(order_item)
        session.state = CallState.TAKING_ORDER
    elif action == "confirm_order":
        session.state = CallState.CONFIRMING_ORDER
    elif action == "send_payment":
        session.state = CallState.PAYMENT_SENT
    elif action == "end_call":
        session.state = CallState.DONE

    return session
