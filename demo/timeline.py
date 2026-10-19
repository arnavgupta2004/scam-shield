"""
The demo video, scene by scene. Narration is what you read in the voiceover;
it is also turned into captions (captions.srt) and a timed script (voiceover.txt).

kind:
  anim     - an animated card rendered frame by frame (animate.py): hook, arch, headline
  slide    - a still from demo/assets/slides/<name>.png, with a slow push-in
  card     - a still rendered at build time from real repo data (bob_card)
  scene    - a live recording of the app (record.py); callouts appear at recorded moments
  bobshell - moments from your demo/clips/bob_shell.mp4 (see BOB_SHELL), skipped if missing
seconds: minimum time on screen; recordings run as long as they need.
callouts: (moment, text); a moment is a mark from record.py ('verdict', 'verdict+2'),
  an agent call ('call0.start') or seconds into the recording.
"""

SCENES = [
    {"kind": "anim", "name": "hook", "seconds": 10,
     "say": "“You are under digital arrest. Tell no one.” Calls like this take a senior’s life savings in minutes. "
            "Scam Shield gives them a second opinion first."},
    {"kind": "slide", "name": "cover", "seconds": 6,
     "say": "Scam Shield is for Bengaluru’s senior citizens, in Kannada, Hindi and English. Built with IBM Bob."},
    {"kind": "slide", "name": "problem", "seconds": 8,
     "say": "Digital arrest, power-cut threats, a grandson on a new number: every one rushes the victim and cuts them off from family."},
    {"kind": "scene", "name": "check_en", "seconds": 14,
     "title": "Check a message", "sub": "A “digital arrest” SMS, shared from WhatsApp",
     "callouts": [("shared", "Shared straight from WhatsApp"),
                  ("call0.start", "Sent to four IBM watsonx Orchestrate agents"),
                  ("verdict", "Scam: why, and exactly what to do"),
                  ("sent", "Phone number and OTP were masked first")],
     "say": "A suspicious message? Share it straight from WhatsApp. The phone number and OTP are masked on the phone, "
            "then watsonx Orchestrate agents decide. Red: a scam, why, and exactly what to do."},
    {"kind": "scene", "name": "screenshot", "seconds": 10,
     "title": "Check a screenshot", "sub": "A power-cut threat that arrived as an image",
     "callouts": [("ocr_start", "Text read on the phone itself"),
                  ("ocr_done", "The image is never uploaded"),
                  ("verdict", "Same agents, same check")],
     "say": "Scam arrived as a picture? The text is read on the phone itself, and the image never leaves it. Same agents, same verdict."},
    {"kind": "scene", "name": "call_kn", "seconds": 16,
     "title": "“I’m on a call right now”", "sub": "ಕನ್ನಡ · no typing during a call",
     "callouts": [("cues", "Tap what the caller is saying"),
                  ("verdict", "Answer in Kannada: hang up now"),
                  ("verdict+2", "One tap calls the family"),
                  ("report", "How to report: 1930 and cybercrime.gov.in")],
     "say": "Still on the call? There’s no time to type, so tap what the caller is saying. The answer comes back in Kannada: "
            "hang up now. One tap calls the family, and the steps to report are right there."},
    {"kind": "scene", "name": "alert", "seconds": 13,
     "title": "Alert my family", "sub": "Only after the user says yes",
     "callouts": [("verdict", "Scam found"),
                  ("confirm", "Nothing is drafted without a yes"),
                  ("ready", "The guardian agent writes it; the user sends it")],
     "say": "Alerting family needs the user’s yes, and the guardian agent’s tool refuses without it. "
            "It writes the message; the user presses send. The number never leaves the phone."},
    {"kind": "scene", "name": "genuine", "seconds": 7,
     "title": "No false alarm", "sub": "A real bank OTP message",
     "callouts": [("verdict", "Genuine message: marked safe")],
     "say": "And it doesn’t cry wolf: a real bank OTP message is marked safe."},
    {"kind": "scene", "name": "tricks", "seconds": 7,
     "title": "Know the tricks", "sub": "हिन्दी · learn the patterns before a scam arrives",
     "callouts": [("cards", "14 cards in Hindi, Kannada and English")],
     "say": "Before any scam arrives, short cards teach the common tricks, in all three languages."},
    {"kind": "anim", "name": "arch", "seconds": 14,
     "say": "Under the hood: private numbers are masked on the device. A triage agent on watsonx Orchestrate hands off "
            "to a scam analyst grounded in a playbook knowledge base; guardian and report helper act only on a tap."},
    {"kind": "card", "name": "bob_card", "seconds": 10,
     "say": "I built it with IBM Bob: Plan mode wrote the build plan, and Agent mode built each tool test-first "
            "and set up the four agents."},
    {"kind": "bobshell", "name": "bob_shell", "seconds": 0,
     "say": "Then Bob reviewed the app layer it hadn’t written: twenty-one findings, with severity, file and line. "
            "I checked each one and accepted eight, and Bob fixed them in Agent mode, reading the code and running the tests first."},
    {"kind": "slide", "name": "bobstory", "seconds": 10,
     "say": "Bob went on to build WhatsApp sharing, on-device screenshot reading, one-tap family calls, the awareness cards, "
            "and browser tests in CI."},
    {"kind": "anim", "name": "headline", "seconds": 10,
     "say": "On twenty-two scam messages it had never seen, keyword rules caught four. Scam Shield caught twenty-one, "
            "with a median answer of about four seconds."},
    {"kind": "slide", "name": "results", "seconds": 6,
     "say": "One false alarm in eighteen genuine messages, and we publish every miss."},
    {"kind": "anim", "name": "close", "seconds": 7,
     "say": "When in doubt, check first. The code and full results are on GitHub."},
]

# Moments from demo/clips/bob_shell.mp4 (2940x1912 screen recording): seconds, speed-up,
# crop (x, y, w, h) and areas to blank out (in crop coordinates), e.g. the signed-in e-mail.
BOB_SHELL = [
    {"from": 5, "to": 9.3, "speed": 1, "crop": (30, 680, 1170, 1210),
     "kicker": "Bob Shell · Ask mode",
     "title": "Bob reviewed the app layer it hadn’t written: 21 findings by severity, file and line"},
    {"from": 17.5, "to": 26, "speed": 2, "crop": (0, 170, 2940, 1080), "hide": [(30, 815, 640, 50)],
     "kicker": "Bob Shell · Agent mode · 2× speed",
     "title": "“Fix the high and medium findings from your review… add tests, run pytest, commit.”"},
    {"from": 46, "to": 64, "speed": 2.5, "crop": (0, 450, 2200, 790),
     "kicker": "Bob Shell · Agent mode · 2.5× speed",
     "title": "Bob reads every file involved, then runs the test suite before changing anything"},
]

# Test messages (from eval/eval_set.csv) used in the recorded scenes.
ROW1 = ("This is Inspector Rao from Mumbai Cyber Crime. Your Aadhaar is linked to a money laundering case. "
        "You are under digital arrest. Stay on video call and do not inform anyone or you will be jailed. "
        "Call +91 98765 43210 and share the OTP 482913.")
ROW37 = "123456 is your OTP for login to SBI YONO. Valid for 5 mins. Do not share OTP with anyone. -SBI"

# A sample SMS screenshot for the screenshot scene (rendered at record time, then read by on-device OCR).
SAMPLE_SMS = """<html><body style="margin:0;background:#E9EDF2;font-family:Arial,sans-serif">
<div style="padding:28px 24px">
<p style="margin:0 0 14px;font-size:22px;color:#55606E;font-weight:bold">VM-ELECTR · SMS</p>
<div style="background:#FFFFFF;border-radius:22px;padding:24px 26px;font-size:30px;line-height:1.4;color:#111">
Dear Consumer, your electricity power will be disconnected tonight at 9.30 PM because your previous month bill
was not updated. Please immediately contact our electricity officer 97xxxxxx40.</div>
<p style="margin:10px 0 0;font-size:20px;color:#7A8594;text-align:right">8:42 PM</p>
</div></body></html>"""

