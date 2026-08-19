"""
Plivo IVR demo.

Flow:
  /trigger-call  (you POST here, or click the button on /)
        |
        v
  /answer   -> GetDigits(4) for OTP -----------------\
                    |                                  |
              correct OTP                        wrong / no OTP
                    |                                  |
                    v                                  v
             /otp (redirect target)           /otp re-renders the
                    |                          same OTP prompt (loop)
                    v
          /language -> GetDigits(1): 1=English, 2=Spanish
                    |
           invalid digit -> /language re-renders same menu (loop)
                    |
                    v
            /action?lang=.. -> GetDigits(1): 1=Play audio, 2=Dial associate
                    |
           invalid digit -> /action re-renders same menu (loop), lang preserved
                    |
          -----------------------------
          |                            |
       Play(mp3) + Speak goodbye   Dial(associate number)

State note: Plivo webhooks are stateless HTTP calls. The only piece of
state we need to carry forward is the caller's language choice, and we do
that via a query string on the action URL (?lang=en / ?lang=es) rather
than a database or in-memory store, per the assignment's "no database
needed" note. CallUUID is available on every webhook if you ever need a
per-call server-side store instead.
"""

from flask import Flask, request, render_template, jsonify
import plivo

import config

app = Flask(__name__)

XML_HEADERS = {"Content-Type": "text/xml"}

COPY = {
    "en": {
        "otp_prompt": "Welcome to Inspire Works. Please enter your 4 digit O T P.",
        "otp_wrong": "Incorrect O T P. Please try again.",
        "lang_prompt": "Press 1 for English. Press 2 for Spanish.",
        "lang_invalid": "Sorry, that is not a valid option.",
        "action_prompt": "Press 1 to play a short audio message. Press 2 to connect to a live associate.",
        "action_invalid": "Sorry, that is not a valid option.",
        "goodbye": "Thank you for calling. Goodbye.",
        "connecting": "Connecting you to a live associate now.",
    },
    "es": {
        "otp_prompt": "Bienvenido a Inspire Works. Por favor ingrese su O T P de 4 digitos.",
        "otp_wrong": "O T P incorrecto. Por favor intente de nuevo.",
        "lang_prompt": "",  # not needed after language is already chosen
        "lang_invalid": "",
        "action_prompt": "Presione 1 para escuchar un mensaje de audio. Presione 2 para conectar con un asociado en vivo.",
        "action_invalid": "Lo siento, esa no es una opcion valida.",
        "goodbye": "Gracias por llamar. Adios.",
        "connecting": "Conectandolo con un asociado en vivo ahora.",
    },
}


def otp_prompt_xml(error=False):
    """OTP GetDigits block. Re-used both for the first prompt and for every
    wrong-answer retry -- that reuse *is* the retry loop, since Plivo has no
    native 'keep looping' primitive; we just keep returning this same block
    from whichever handler receives a wrong answer."""
    lead_in = f"<Speak>{COPY['en']['otp_wrong']}</Speak>" if error else ""
    return (
        f"<Response>"
        f"{lead_in}"
        f'<GetDigits action="{config.PUBLIC_BASE_URL}/otp" method="POST" '
        f'numDigits="4" timeout="15" retries="1">'
        f"<Speak>{COPY['en']['otp_prompt']}</Speak>"
        f"</GetDigits>"
        # If GetDigits gets no input at all (timeout with no retries left),
        # execution falls through to here -- loop back to /answer to start over.
        f'<Redirect method="GET">{config.PUBLIC_BASE_URL}/answer</Redirect>'
        f"</Response>"
    )


def language_menu_xml(error=False):
    lead_in = f"<Speak>{COPY['en']['lang_invalid']}</Speak>" if error else ""
    return (
        f"<Response>"
        f"{lead_in}"
        f'<GetDigits action="{config.PUBLIC_BASE_URL}/language" method="POST" '
        f'numDigits="1" timeout="15" retries="1">'
        f"<Speak>{COPY['en']['lang_prompt']}</Speak>"
        f"</GetDigits>"
        f'<Redirect method="GET">{config.PUBLIC_BASE_URL}/language</Redirect>'
        f"</Response>"
    )


def action_menu_xml(lang, error=False):
    c = COPY.get(lang, COPY["en"])
    lead_in = f"<Speak>{c['action_invalid']}</Speak>" if error else ""
    action_url = f"{config.PUBLIC_BASE_URL}/action?lang={lang}"
    return (
        f"<Response>"
        f"{lead_in}"
        f'<GetDigits action="{action_url}" method="POST" '
        f'numDigits="1" timeout="15" retries="1">'
        f"<Speak>{c['action_prompt']}</Speak>"
        f"</GetDigits>"
        f'<Redirect method="GET">{action_url}</Redirect>'
        f"</Response>"
    )


@app.route("/trigger-call", methods=["POST"])
def trigger_call():
    """Kicks off the outbound call. Reads target number from JSON body if
    provided, otherwise falls back to TARGET_PHONE_NUMBER in .env."""
    config.check_config()
    data = request.get_json(silent=True) or {}
    to_number = data.get("to") or config.TARGET_PHONE_NUMBER

    client = plivo.RestClient(config.PLIVO_AUTH_ID, config.PLIVO_AUTH_TOKEN)
    response = client.calls.create(
        from_=config.PLIVO_FROM_NUMBER,
        to_=to_number,
        answer_url=f"{config.PUBLIC_BASE_URL}/answer",
        answer_method="GET",
    )
    return jsonify(
        {
            "status": "call_initiated",
            "to": to_number,
            "request_uuid": getattr(response, "request_uuid", None),
        }
    )


@app.route("/answer", methods=["GET", "POST"])
def answer():
    return otp_prompt_xml(error=False), 200, XML_HEADERS


@app.route("/otp", methods=["GET", "POST"])
def otp():
    digits = request.values.get("Digits", "")
    if digits == config.OTP_CODE:
        return language_menu_xml(error=False), 200, XML_HEADERS
    # Wrong OTP (or no digits captured) -> re-prompt, this is the loop.
    return otp_prompt_xml(error=True), 200, XML_HEADERS


@app.route("/language", methods=["GET", "POST"])
def language():
    digits = request.values.get("Digits", "")
    if digits == "1":
        return action_menu_xml("en", error=False), 200, XML_HEADERS
    if digits == "2":
        return action_menu_xml("es", error=False), 200, XML_HEADERS
    return language_menu_xml(error=True), 200, XML_HEADERS


@app.route("/action", methods=["GET", "POST"])
def action():
    lang = request.args.get("lang", "en")
    digits = request.values.get("Digits", "")
    c = COPY.get(lang, COPY["en"])

    if digits == "1":
        xml = (
            f"<Response>"
            f"<Play>{config.AUDIO_MESSAGE_URL}</Play>"
            f"<Speak>{c['goodbye']}</Speak>"
            f"<Hangup/>"
            f"</Response>"
        )
        return xml, 200, XML_HEADERS

    if digits == "2":
        xml = (
            f"<Response>"
            f"<Speak>{c['connecting']}</Speak>"
            f"<Dial><Number>{config.ASSOCIATE_NUMBER}</Number></Dial>"
            f"</Response>"
        )
        return xml, 200, XML_HEADERS

    return action_menu_xml(lang, error=True), 200, XML_HEADERS


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


if __name__ == "__main__":
    # Port 5000 is often taken on macOS by the AirPlay Receiver service,
    # so we default to 5001 instead.
    app.run(host="0.0.0.0", port=5001, debug=True)
