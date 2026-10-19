"""
The demo video, scene by scene. Narration is what you read in the voiceover;
it is also turned into captions (captions.srt) and a timed script (voiceover.txt).

kind:
  slide  - a still from demo/assets/slides/<name>.png
  card   - a still rendered at build time from real repo data (bob_card)
  scene  - a live recording of the app (recorded by record.py)
  clip   - your own recording, used only if demo/clips/<name>.mp4 exists
seconds: minimum time on screen; recordings run as long as they need.
"""

SCENES = [
    {"kind": "slide", "name": "cover", "seconds": 13,
     "say": "A scam call can take a senior’s savings in minutes, before they think to call anyone. "
            "Scam Shield gives Bengaluru’s senior citizens a second opinion in that moment, in Kannada, Hindi or English."},
    {"kind": "slide", "name": "problem", "seconds": 11,
     "say": "Digital arrest, power-cut threats, a grandson on a new number. They all rush and isolate the victim."},
    {"kind": "slide", "name": "need", "seconds": 10,
     "say": "So help has to come in seconds, in their language, even while the call is still going, and without sharing anything private."},
    {"kind": "scene", "name": "check_en", "seconds": 26,
     "title": "Check a message", "sub": "English · a “digital arrest” SMS",
     "say": "Paste or speak the message. Scam Shield masks private numbers, here the phone number and OTP, "
            "before anything reaches an AI model, then IBM watsonx Orchestrate agents decide. "
            "Red: this looks like a scam, why, and exactly what to do."},
    {"kind": "scene", "name": "call_kn", "seconds": 24,
     "title": "“I’m on a call right now”", "sub": "ಕನ್ನಡ · tap what the caller is saying",
     "say": "During a call there’s no time to type. Tap what the caller is saying, "
            "and the answer comes back in Kannada, read aloud: hang up now."},
    {"kind": "scene", "name": "alert", "seconds": 15,
     "title": "Alert my family", "sub": "Only after the user says yes",
     "say": "Alerting family needs the user’s yes, and the agent’s tool refuses without it. "
            "The user presses send themselves; the number never leaves the phone."},
    {"kind": "scene", "name": "genuine", "seconds": 10,
     "title": "No false alarm", "sub": "A real bank OTP message",
     "say": "And it doesn’t cry wolf: a real bank OTP message is marked safe."},
    {"kind": "card", "name": "bob_card", "seconds": 16,
     "say": "I built the plan, the tools and the four agents with IBM Bob. Bob’s Plan mode read the scam playbooks "
            "and wrote the build plan; Agent mode built each tool test-first and set up the Orchestrate agents from the ADK docs."},
    {"kind": "clip", "name": "bob_shell", "seconds": 0, "say": ""},
    {"kind": "slide", "name": "bobstory", "seconds": 14,
     "say": "When knowledge-base indexing failed, Bob stopped and built a fallback tool. "
            "After the trial credits ran out, I built the web app and API without Bob."},
    {"kind": "slide", "name": "headline", "seconds": 12,
     "say": "On 22 scam messages it had never seen, keyword rules caught 4. Scam Shield caught 21, in about four seconds."},
    {"kind": "slide", "name": "results", "seconds": 11,
     "say": "One false alarm in 18 genuine messages, and we publish the misses too."},
    {"kind": "slide", "name": "close", "seconds": 8,
     "say": "When in doubt, check first. The code and full results are on GitHub."},
]

# Test messages (from eval/eval_set.csv) used in the recorded scenes.
ROW1 = ("This is Inspector Rao from Mumbai Cyber Crime. Your Aadhaar is linked to a money laundering case. "
        "You are under digital arrest. Stay on video call and do not inform anyone or you will be jailed. "
        "Call +91 98765 43210 and share the OTP 482913.")
ROW37 = "123456 is your OTP for login to SBI YONO. Valid for 5 mins. Do not share OTP with anyone. -SBI"
