"""Local, fast, offline intent matcher for Fox, the voice assistant (module keeps its
internal `guide_*` name; "Fox" is the spoken/display name the user actually hears).

Most of the fixed command list ("Start scan", "Retake", "Repeat that", "Louder", "Stop",
"Skip guide", "Mute", ...) never needs to leave the device at all -- matching a short
transcript against a known phrase list is near-instant, which is what keeps local-command
latency under the <1.5s target. Only when nothing here matches with enough confidence does
`core.guide_service` fall back to the LLM (`core.guide_llm`).

Phrases are provided for English, Hindi and Marathi. The Hindi/Marathi lines are a
good-faith, commonly-used phrasing for each command -- not professionally reviewed
translations -- see the "assumptions / left as TODO" note in README.md.
"""

import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.guide_schema import ActionType, Lang


def normalize(text: str) -> str:
    """Lowercase and strip punctuation, keeping letters, numbers, whitespace, and combining
    marks -- plain `\\w` strips Devanagari vowel signs (category Mn), which would silently
    turn "रुको" (stop) into "रक" and lose the word's actual shape."""
    out = []
    for ch in text.lower():
        if ch.isspace() or unicodedata.category(ch)[0] in ("L", "N", "M"):
            out.append(ch)
    return "".join(out).strip()


@dataclass
class IntentDef:
    type: ActionType
    phrases: Dict[str, List[str]]
    speech: Dict[str, str]
    needs_confirmation: bool = False


@dataclass
class IntentMatch:
    type: ActionType
    confidence: float
    speech: str
    needs_confirmation: bool = False
    source: str = "intent"


INTENTS: List[IntentDef] = [
    IntentDef(
        type="start_scan",
        phrases={
            "en": ["start a scan", "start scan", "new scan", "scan my face", "take a scan", "begin a scan", "begin scan"],
            "hi": ["स्कैन शुरू करो", "नया स्कैन", "स्कैन करो", "स्कैन शुरू करें"],
            "mr": ["स्कॅन सुरू करा", "नवीन स्कॅन", "स्कॅन करा"],
        },
        speech={"en": "Let's do this together! Look straight at the camera and hold still for me.",
                "hi": "चलो, एक स्कैन करते हैं! कैमरे की तरफ देखो और ज़रा स्थिर रहना।",
                "mr": "चल, एक स्कॅन करूया! कॅमेऱ्याकडे बघ आणि जरा स्थिर राहा."},
    ),
    IntentDef(
        type="retake_photo",
        phrases={
            "en": ["retake", "take it again", "retake photo", "try again", "retake the photo"],
            "hi": ["फिर से लो", "दोबारा लो", "फिर से फोटो लो"],
            "mr": ["पुन्हा घ्या", "पुन्हा फोटो घ्या"],
        },
        speech={"en": "No worries at all, let's try that again. Get ready!",
                "hi": "कोई बात नहीं, फिर से कोशिश करते हैं। तैयार हो जाओ।",
                "mr": "काही हरकत नाही, पुन्हा प्रयत्न करूया. तयार हो."},
    ),
    IntentDef(
        type="explain_score",
        phrases={
            "en": ["what does my score mean", "explain my score", "what is my score", "explain score", "what does the score mean"],
            "hi": ["मेरा स्कोर क्या मतलब है", "स्कोर समझाओ", "मेरा स्कोर क्या है"],
            "mr": ["माझा स्कोर काय आहे", "स्कोर समजावून सांगा"],
        },
        speech={"en": "Of course, let me walk you through it.",
                "hi": "हां बिल्कुल, मैं तुम्हें तुम्हारा स्कोर समझाती हूं।",
                "mr": "हो नक्कीच, मी तुला तुझा स्कोर समजावून सांगते."},
    ),
    IntentDef(
        type="show_last_scan",
        phrases={
            "en": ["show my last scan", "last scan", "show last scan", "my previous scan", "show my previous scan"],
            "hi": ["मेरा पिछला स्कैन दिखाओ", "पिछला स्कैन"],
            "mr": ["माझा मागील स्कॅन दाखवा", "मागील स्कॅन"],
        },
        speech={"en": "Here's your last scan, right here.",
                "hi": "ये रहा तुम्हारा पिछला स्कैन।",
                "mr": "हा आहे तुझा मागील स्कॅन."},
    ),
    IntentDef(
        type="navigate_diary",
        phrases={
            "en": ["open my diary", "open diary", "show diary", "skin diary", "open the diary"],
            "hi": ["डायरी खोलो", "मेरी डायरी खोलो"],
            "mr": ["डायरी उघडा", "माझी डायरी उघडा"],
        },
        speech={"en": "Opening your skin diary for you.", "hi": "तुम्हारी डायरी खोल रही हूं।", "mr": "तुझी डायरी उघडत आहे."},
    ),
    IntentDef(
        type="compare_last_week",
        phrases={
            "en": ["compare with last week", "compare to last week", "compare last week"],
            "hi": ["पिछले हफ्ते से तुलना करो", "पिछले हफ्ते की तुलना"],
            "mr": ["मागील आठवड्याशी तुलना करा"],
        },
        speech={"en": "Let's see how you're doing compared to last week.", "hi": "चलो देखते हैं पिछले हफ्ते से क्या बदला।", "mr": "चल बघूया मागील आठवड्यापासून काय बदललं."},
    ),
    IntentDef(
        type="repeat",
        phrases={
            "en": ["repeat that", "say that again", "repeat", "what did you say", "can you repeat that"],
            "hi": ["फिर से कहो", "दोबारा कहो"],
            "mr": ["पुन्हा सांगा"],
        },
        speech={"en": "", "hi": "", "mr": ""},
    ),
    IntentDef(
        type="louder",
        phrases={
            "en": ["louder", "speak louder", "volume up", "turn it up"],
            "hi": ["तेज आवाज़", "आवाज़ बढ़ाओ"],
            "mr": ["आवाज वाढवा"],
        },
        speech={"en": "Sure thing, a little louder now.", "hi": "ठीक है, थोड़ा तेज़ बोलती हूं।", "mr": "ठीक आहे, जरा मोठ्याने बोलते."},
    ),
    IntentDef(
        type="quieter",
        phrases={
            "en": ["quieter", "speak softer", "volume down", "lower your voice", "turn it down"],
            "hi": ["आवाज़ कम करो", "धीरे बोलो"],
            "mr": ["आवाज कमी करा"],
        },
        speech={"en": "Got it, I'll keep it down.", "hi": "ठीक है, धीरे बोलती हूं।", "mr": "ठीक आहे, हळू बोलते."},
    ),
    IntentDef(
        type="stop_speaking",
        phrases={
            "en": ["stop", "stop talking", "be quiet", "stop speaking"],
            "hi": ["रुको", "बंद करो", "चुप हो जाओ"],
            "mr": ["थांबा", "बंद करा"],
        },
        speech={"en": "", "hi": "", "mr": ""},
    ),
    IntentDef(
        type="mute",
        phrases={
            "en": ["mute", "turn off voice", "mute yourself", "mute the voice"],
            "hi": ["म्यूट करो", "आवाज़ बंद करो"],
            "mr": ["म्यूट करा", "आवाज बंद करा"],
        },
        speech={"en": "Okay, going quiet. Just tap the mic whenever you want me back.",
                "hi": "ठीक है, चुप हो जाती हूं। जब चाहो माइक दबाकर बुला लेना।",
                "mr": "ठीक आहे, गप्प होते. हवं तेव्हा माइक दाबून बोलव."},
    ),
    IntentDef(
        type="unmute",
        phrases={
            "en": ["unmute", "turn on voice", "unmute yourself", "unmute the voice"],
            "hi": ["अनम्यूट करो", "आवाज़ चालू करो"],
            "mr": ["अनम्यूट करा", "आवाज सुरू करा"],
        },
        speech={"en": "I'm back! Miss me?", "hi": "मैं वापस आ गई! याद किया मुझे?", "mr": "मी परत आले! आठवण आली का?"},
    ),
    IntentDef(
        type="skip_guide",
        phrases={
            "en": ["skip guide", "skip the guide", "no thanks", "skip this"],
            "hi": ["गाइड छोड़ो", "गाइड स्किप करो"],
            "mr": ["गाईड वगळा"],
        },
        speech={"en": "No problem, I'll stay quiet unless you need me.",
                "hi": "कोई बात नहीं, ज़रूरत पड़ने पर ही बोलूंगी।",
                "mr": "काही हरकत नाही, गरज असेल तेव्हाच बोलेन."},
    ),
    IntentDef(
        type="navigate_routine",
        phrases={"en": ["open my routine", "show my routine", "open routine"], "hi": ["रूटीन खोलो"], "mr": ["रुटीन उघडा"]},
        speech={"en": "Here's your routine.", "hi": "ये रहा तुम्हारा रूटीन।", "mr": "हा आहे तुझा रुटीन."},
    ),
    IntentDef(
        type="navigate_shop",
        phrases={"en": ["open the shop", "open shop", "show products"], "hi": ["दुकान खोलो", "शॉप खोलो"], "mr": ["शॉप उघडा"]},
        speech={"en": "Let's see what's in the shop.", "hi": "चलो शॉप देखते हैं।", "mr": "चल शॉप बघूया."},
    ),
    IntentDef(
        type="navigate_ingredient_check",
        phrases={"en": ["check ingredients", "check my ingredients", "ingredient check"],
                 "hi": ["इंग्रेडिएंट चेक करो"], "mr": ["इंग्रेडियंट तपासा"]},
        speech={"en": "Opening the ingredient checker for you.", "hi": "इंग्रेडिएंट चेक खोल रही हूं।", "mr": "इंग्रेडियंट तपासणी उघडत आहे."},
    ),
    IntentDef(
        type="navigate_history",
        phrases={"en": ["show my history", "open history", "scan history"], "hi": ["इतिहास दिखाओ"], "mr": ["इतिहास दाखवा"]},
        speech={"en": "Here's your scan history.", "hi": "ये रहा तुम्हारा इतिहास।", "mr": "हा आहे तुझा इतिहास."},
    ),
    IntentDef(
        type="navigate_privacy",
        phrases={"en": ["open privacy", "privacy settings", "my privacy"], "hi": ["प्राइवेसी खोलो"], "mr": ["प्रायव्हसी उघडा"]},
        speech={"en": "Opening your privacy settings.", "hi": "प्राइवेसी सेटिंग्स खोल रही हूं।", "mr": "प्रायव्हसी सेटिंग्ज उघडत आहे."},
    ),
    IntentDef(
        type="navigate_settings",
        phrases={"en": ["open settings", "go to settings"], "hi": ["सेटिंग्स खोलो"], "mr": ["सेटिंग्ज उघडा"]},
        speech={"en": "Here are your settings.", "hi": "ये रहीं तुम्हारी सेटिंग्स।", "mr": "ह्या आहेत तुझ्या सेटिंग्ज."},
    ),
    IntentDef(
        type="navigate_dashboard",
        phrases={"en": ["go home", "go to dashboard", "open dashboard"], "hi": ["डैशबोर्ड खोलो", "होम जाओ"], "mr": ["डॅशबोर्ड उघडा", "होम वर जा"]},
        speech={"en": "Taking you home.", "hi": "घर चलते हैं।", "mr": "घरी जाऊया."},
    ),
    IntentDef(
        type="navigate_analysis",
        phrases={"en": ["show my analysis", "open analysis", "show results", "show my results"],
                 "hi": ["एनालिसिस खोलो", "रिजल्ट दिखाओ"], "mr": ["विश्लेषण उघडा", "रिझल्ट दाखवा"]},
        speech={"en": "Here's your analysis.", "hi": "ये रहा तुम्हारा एनालिसिस।", "mr": "हे आहे तुझं विश्लेषण."},
    ),
    IntentDef(
        type="wipe_data",
        phrases={
            "en": ["delete all my data", "wipe my data", "erase everything", "delete everything"],
            "hi": ["मेरा सारा डेटा मिटाओ", "सब डेटा डिलीट करो"],
            "mr": ["माझा सर्व डेटा काढा", "सर्व डेटा डिलीट करा"],
        },
        speech={"en": "Wait, are you sure? This will delete every scan, photo, and setting for good.",
                "hi": "रुको, पक्का? इससे तुम्हारे सारे स्कैन, फोटो और सेटिंग्स हमेशा के लिए मिट जाएंगी।",
                "mr": "थांब, नक्की ना? यामुळे तुझे सर्व स्कॅन, फोटो आणि सेटिंग्ज कायमचे हटतील."},
        needs_confirmation=True,
    ),
]


def _score(norm_text: str, norm_phrase: str) -> float:
    if not norm_phrase:
        return 0.0
    if norm_text == norm_phrase:
        return 0.97
    if norm_phrase in norm_text:
        return 0.85
    if norm_text in norm_phrase:
        return 0.75
    phrase_words = set(norm_phrase.split())
    text_words = set(norm_text.split())
    if not phrase_words:
        return 0.0
    if phrase_words <= text_words:
        return 0.7
    overlap = phrase_words & text_words
    return 0.55 * (len(overlap) / len(phrase_words)) if overlap else 0.0


def match(text: str, lang: Lang = "en") -> Optional[IntentMatch]:
    """Best-matching intent for one transcript, or None if nothing scores above 0."""
    norm_text = normalize(text)
    if not norm_text:
        return None
    best: Optional[IntentMatch] = None
    for intent in INTENTS:
        for phrase in intent.phrases.get(lang, []):
            conf = _score(norm_text, normalize(phrase))
            if conf <= 0:
                continue
            if best is None or conf > best.confidence:
                best = IntentMatch(
                    type=intent.type, confidence=conf,
                    speech=intent.speech.get(lang, intent.speech.get("en", "")),
                    needs_confirmation=intent.needs_confirmation,
                )
    return best
