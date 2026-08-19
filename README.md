# Plivo IVR Demo — FDE Technical Assignment

A demo IVR that places an outbound call, authenticates the caller with a
hardcoded-OTP DTMF prompt, then routes through a two-level voice menu
(language, then action) using Plivo XML.

## What it does

1. Calls your phone from the given Plivo number.
2. On answer, asks for a 4-digit OTP (your birthdate, DDMM). Wrong entries
   re-prompt indefinitely until correct.
3. Once authenticated: Level 1 asks for a language (1 = English, 2 = Spanish).
4. Level 2 asks for an action: 1 = play a short audio clip, 2 = forward the
   call to a placeholder "live associate" number.
5. Invalid input at any stage re-prompts the current menu instead of failing.

## Requirements

- Python 3.11+ (3.12 recommended; very new Python versions may lack wheels
  for some dependencies)
- A Plivo account with Auth ID + Auth Token, and a Plivo phone number
- [ngrok](https://ngrok.com) (or any tunnel/public host) to expose your
  local server to Plivo's webhooks

## Setup

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:

| Variable | Description |
|---|---|
| `PLIVO_AUTH_ID` | From your Plivo console |
| `PLIVO_AUTH_TOKEN` | From your Plivo console |
| `PLIVO_FROM_NUMBER` | The Plivo number placing the call |
| `TARGET_PHONE_NUMBER` | Your phone number, receiving the call (E.164, e.g. `+9198XXXXXXXX`) |
| `PUBLIC_BASE_URL` | Your current ngrok HTTPS URL, no trailing slash |
| `OTP_CODE` | Your birthdate in DDMM, e.g. March 15 → `1503` |
| `ASSOCIATE_NUMBER` | Placeholder "live associate" number |
| `AUDIO_MESSAGE_URL` | (optional) public MP3 URL; defaults to a public sample track |

## Run

Terminal 1:
```bash
python app.py
```
Runs on `http://localhost:5001` (5000 is often taken by macOS AirPlay Receiver).

Terminal 2:
```bash
ngrok http 5001
```
Copy the `https://...ngrok-free.app` (or `.dev`) forwarding URL into
`PUBLIC_BASE_URL` in `.env`, then restart `app.py` so it picks up the change.

## Trigger a call

Either open `http://localhost:5001/` in a browser and click **Call Me**, or:

```bash
curl -X POST http://localhost:5001/trigger-call \
  -H "Content-Type: application/json" -d '{}'
```

Optionally override the target number per-request:
```bash
curl -X POST http://localhost:5001/trigger-call \
  -H "Content-Type: application/json" \
  -d '{"to": "+9198XXXXXXXX"}'
```

## Testing checklist

Logic verified via direct curl calls against the running Flask app (bypassing
Plivo entirely — see "Dry-run testing" below). Live-call items remain
unchecked pending working Plivo credentials.

- [x] `/answer` returns the OTP `<GetDigits>` prompt
- [x] Wrong OTP → re-prompted with "Incorrect OTP" message (retry loop)
- [x] Correct OTP → advances to the Level 1 language menu
- [x] Language: Press 1 → English Level 2 menu (`?lang=en`)
- [x] Language: Press 2 → Spanish Level 2 menu (`?lang=es`)
- [x] Language: invalid digit → re-prompts with "not a valid option"
- [x] Level 2, press 1 → `<Play>` audio, goodbye `<Speak>`, `<Hangup/>`
- [x] Level 2, press 2 → `<Dial><Number>` to `ASSOCIATE_NUMBER`
- [x] Level 2: invalid digit → re-prompts, language preserved
- [ ] Call rings and answers with the OTP prompt (blocked on valid Plivo credentials)
- [ ] Full live call walked through end-to-end (OTP → Level 1 → Level 2)

## Dry-run testing (no live call required)

Every route can be exercised directly with curl, simulating exactly what
Plivo would POST at each step. Useful for verifying logic changes without
waiting on a live call or valid Plivo credentials.

```bash
# Simulate call answer
curl -s http://localhost:5001/answer

# Simulate wrong OTP, then correct OTP
curl -s -X POST http://localhost:5001/otp -d "Digits=9999"
curl -s -X POST http://localhost:5001/otp -d "Digits=1407"   # use your real OTP_CODE

# Simulate language selection (1 = English, 2 = Spanish, invalid e.g. 9)
curl -s -X POST http://localhost:5001/language -d "Digits=1"
curl -s -X POST http://localhost:5001/language -d "Digits=9"

# Simulate Level 2 action (1 = play audio, 2 = dial associate, invalid e.g. 9)
curl -s -X POST "http://localhost:5001/action?lang=en" -d "Digits=1"
curl -s -X POST "http://localhost:5001/action?lang=en" -d "Digits=2"
curl -s -X POST "http://localhost:5001/action?lang=en" -d "Digits=9"
```

Each response is the exact Plivo XML that would be returned to a live call.

## How call state is carried across requests

Plivo webhooks are stateless HTTP calls (`/answer` → `/otp` → `/language` →
`/action` are independent requests). The only state we need across steps is
the caller's language choice, which is passed via the `action` URL's query
string (`/action?lang=en`) rather than a database, per the assignment note
that no database is required. `CallUUID` is available on every webhook if
you need a more robust per-call server-side store instead.

## Notes

- `.env` is git-ignored — never commit real credentials.
- The audio file for the "press 1" branch is served from a public URL
  (configurable via `AUDIO_MESSAGE_URL`); no local file hosting is required.
- Trial Plivo accounts sometimes restrict outbound calls to verified
  numbers, or prepend a trial-account notice — verify your number in the
  Plivo console if calls don't connect.
