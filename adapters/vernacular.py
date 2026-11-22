"""Plain-language support for clauses already flagged by the deterministic rules."""

from __future__ import annotations

from pathlib import Path
import tempfile
import json
import os
from typing import Any
from urllib.request import Request, urlopen

from gtts import gTTS


_TEMPLATES: dict[str, dict[str, tuple[str, str, str]]] = {
    "TENANCY_DEPOSIT_CAP": {
        "en": ("The deposit is higher than two months' rent. A large deposit can be difficult to recover.", "Please limit the refundable security deposit to two months' rent and return it promptly after handover, less only documented dues or damage beyond normal wear.", "Could we please revise the deposit to two months' rent and record the return timeline and permitted deductions clearly?"),
        "kn": ("ಭದ್ರತಾ ಠೇವಣಿ ಎರಡು ತಿಂಗಳ ಬಾಡಿಗೆಯಿಗಿಂತ ಹೆಚ್ಚು ಇದೆ. ಹೆಚ್ಚಿನ ಠೇವಣಿಯನ್ನು ಮರಳಿ ಪಡೆಯುವುದು ಕಷ್ಟವಾಗಬಹುದು.", "ದಯವಿಟ್ಟು ಮರುಪಾವತಿಸಬಹುದಾದ ಭದ್ರತಾ ಠೇವಣಿಯನ್ನು ಎರಡು ತಿಂಗಳ ಬಾಡಿಗೆಗೆ ಮಿತಿಗೊಳಿಸಿ. ಮನೆ ಹಸ್ತಾಂತರದ ನಂತರ, ದಾಖಲೆಬದ್ಧ ಬಾಕಿ ಅಥವಾ ಸಾಮಾನ್ಯ ಬಳಕೆಯನ್ನು ಮೀರಿದ ಹಾನಿಯನ್ನು ಹೊರತುಪಡಿಸಿ, ಅದನ್ನು ಬೇಗ ಮರುಪಾವತಿಸಿ.", "ಠೇವಣಿಯನ್ನು ಎರಡು ತಿಂಗಳ ಬಾಡಿಗೆಗೆ ಮಿತಿಗೊಳಿಸಿ, ಮರುಪಾವತಿ ಅವಧಿ ಮತ್ತು ಕಡಿತಗಳ ನಿಯಮಗಳನ್ನು ಸ್ಪಷ್ಟವಾಗಿ ಬರೆಯಬಹುದೇ?"),
        "hi": ("सुरक्षा जमा दो महीने के किराए से अधिक है। बड़ी जमा राशि वापस पाना कठिन हो सकता है।", "कृपया वापसी योग्य सुरक्षा जमा दो महीने के किराए तक सीमित रखें। घर सौंपने के बाद, दर्ज बकाया या सामान्य घिसावट से अधिक नुकसान को छोड़कर, इसे शीघ्र लौटाएँ।", "क्या हम जमा राशि दो महीने के किराए तक रखकर वापसी की समय-सीमा और कटौती के नियम स्पष्ट लिख सकते हैं?"),
    },
    "FORFEITURE_PENALTY": {
        "en": ("This term allows the entire deposit to be kept as a penalty, even if the actual loss is smaller.", "If the tenancy ends early, the landlord may deduct only reasonable, documented losses directly caused by the early termination and must refund the remaining deposit.", "Could we replace automatic forfeiture with deductions limited to reasonable, documented loss, and return the balance?"),
        "kn": ("ನಿಜವಾದ ನಷ್ಟ ಕಡಿಮೆಯಿದ್ದರೂ ಸಂಪೂರ್ಣ ಠೇವಣಿಯನ್ನು ದಂಡವಾಗಿ ಇಟ್ಟುಕೊಳ್ಳಲು ಈ ನಿಯಮ ಅವಕಾಶ ನೀಡುತ್ತದೆ.", "ಬಾಡಿಗೆ ಅವಧಿ ಮುಂಚಿತವಾಗಿ ಮುಗಿದರೆ, ಅದರಿಂದ ನೇರವಾಗಿ ಉಂಟಾದ ಸಮಂಜಸ ಮತ್ತು ದಾಖಲೆಬದ್ಧ ನಷ್ಟವನ್ನಷ್ಟೇ ಕಡಿತಗೊಳಿಸಿ, ಉಳಿದ ಠೇವಣಿಯನ್ನು ಮರುಪಾವತಿಸಬೇಕು.", "ಸ್ವಯಂಚಾಲಿತವಾಗಿ ಸಂಪೂರ್ಣ ಠೇವಣಿ ಕಳೆದುಕೊಳ್ಳುವ ಬದಲು, ದಾಖಲೆಬದ್ಧ ನಷ್ಟಕ್ಕೆ ಮಾತ್ರ ಕಡಿತ ಮಾಡಿ ಉಳಿದ ಮೊತ್ತವನ್ನು ಹಿಂದಿರುಗಿಸುವಂತೆ ಬದಲಾಯಿಸಬಹುದೇ?"),
        "hi": ("यह शर्त वास्तविक नुकसान कम होने पर भी पूरी जमा राशि रोकने की अनुमति देती है।", "किरायेदारी समय से पहले समाप्त होने पर केवल उससे सीधे हुए उचित और दर्ज नुकसान की कटौती करें और बाकी जमा राशि लौटाएँ।", "क्या पूरी जमा राशि जब्त करने के बजाय केवल दर्ज वास्तविक नुकसान काटकर बाकी लौटाया जा सकता है?"),
    },
    "EXCESSIVE_LOCKIN": {
        "en": ("The lock-in period is longer than six months, which can limit your ability to move.", "Either party may end the tenancy with 30 days' written notice after the first six months, without an additional lock-in penalty.", "Could we shorten the lock-in to six months and allow either party to end the tenancy with 30 days' written notice?"),
        "kn": ("ಆರು ತಿಂಗಳಿಗಿಂತ ದೀರ್ಘವಾದ ಲಾಕ್-ಇನ್ ಅವಧಿ ನಿಮಗೆ ಸ್ಥಳಾಂತರವಾಗಲು ತೊಂದರೆ ಉಂಟುಮಾಡಬಹುದು.", "ಮೊದಲ ಆರು ತಿಂಗಳ ನಂತರ, ಯಾವುದೇ ಹೆಚ್ಚುವರಿ ಲಾಕ್-ಇನ್ ದಂಡವಿಲ್ಲದೆ, ಎರಡೂ ಪಕ್ಷಗಳು 30 ದಿನಗಳ ಲಿಖಿತ ನೋಟಿಸ್ ನೀಡಿ ಒಪ್ಪಂದವನ್ನು ಮುಕ್ತಾಯಗೊಳಿಸಬಹುದು.", "ಲಾಕ್-ಇನ್ ಅವಧಿಯನ್ನು ಆರು ತಿಂಗಳಿಗೆ ಇಳಿಸಿ, ನಂತರ 30 ದಿನಗಳ ಲಿಖಿತ ನೋಟಿಸ್ ಮೂಲಕ ಮುಕ್ತಾಯಗೊಳಿಸಲು ಅವಕಾಶ ನೀಡಬಹುದೇ?"),
        "hi": ("छह महीने से लंबी लॉक-इन अवधि आपके लिए स्थान बदलना कठिन कर सकती है।", "पहले छह महीनों के बाद, कोई अतिरिक्त लॉक-इन दंड लगाए बिना, कोई भी पक्ष 30 दिन का लिखित नोटिस देकर किरायेदारी समाप्त कर सकता है।", "क्या लॉक-इन अवधि छह महीने करके उसके बाद 30 दिन के लिखित नोटिस से समाप्ति की अनुमति दी जा सकती है?"),
    },
    "UNANNOUNCED_ENTRY": {
        "en": ("The landlord may enter without warning, which affects your privacy and quiet use of the home.", "Except in a genuine emergency, the landlord must give at least 24 hours' notice and obtain the tenant's agreement before entry, at a mutually convenient time.", "Could we add at least 24 hours' notice and agree that visits happen at a mutually convenient time, except for emergencies?"),
        "kn": ("ಮುಂಚಿತ ಮಾಹಿತಿ ಇಲ್ಲದೆ ಮನೆಗೆ ಪ್ರವೇಶಿಸುವುದು ನಿಮ್ಮ ಗೌಪ್ಯತೆ ಮತ್ತು ನೆಮ್ಮದಿಗೆ ಧಕ್ಕೆ ತರಬಹುದು.", "ತುರ್ತು ಪರಿಸ್ಥಿತಿಯನ್ನು ಹೊರತುಪಡಿಸಿ, ಮನೆಗೆ ಪ್ರವೇಶಿಸುವ ಮೊದಲು ಕನಿಷ್ಠ 24 ಗಂಟೆಗಳ ನೋಟಿಸ್ ನೀಡಿ, ಬಾಡಿಗೆದಾರರ ಒಪ್ಪಿಗೆ ಪಡೆದು, ಇಬ್ಬರಿಗೂ ಅನುಕೂಲವಾದ ಸಮಯದಲ್ಲಿ ಬರಬೇಕು.", "ತುರ್ತು ಸಂದರ್ಭಗಳನ್ನು ಹೊರತುಪಡಿಸಿ, ಕನಿಷ್ಠ 24 ಗಂಟೆಗಳ ನೋಟಿಸ್ ಮತ್ತು ಇಬ್ಬರಿಗೂ ಅನುಕೂಲವಾದ ಸಮಯವನ್ನು ಸೇರಿಸಬಹುದೇ?"),
        "hi": ("बिना सूचना घर में प्रवेश करना आपकी निजता और शांतिपूर्ण उपयोग को प्रभावित कर सकता है।", "वास्तविक आपात स्थिति को छोड़कर, मकान मालिक प्रवेश से कम से कम 24 घंटे पहले सूचना दें, किरायेदार की सहमति लें और दोनों के लिए सुविधाजनक समय पर आएँ।", "क्या आपात स्थिति को छोड़कर 24 घंटे की सूचना और दोनों के लिए सुविधाजनक समय की शर्त जोड़ सकते हैं?"),
    },
    "ARBITRARY_PAINTING_DEDUCTION": {
        "en": ("The painting deduction is more than one month's rent and may charge you for ordinary wear.", "Painting costs may be deducted only for damage beyond ordinary wear and tear, supported by receipts; no fixed painting charge applies otherwise.", "Could we limit painting deductions to documented damage beyond normal wear, with no automatic fixed charge?"),
        "kn": ("ಬಣ್ಣ ಹಚ್ಚುವ ವೆಚ್ಚದ ಕಡಿತ ಒಂದು ತಿಂಗಳ ಬಾಡಿಗೆಯಿಗಿಂತ ಹೆಚ್ಚಿದ್ದು, ಸಾಮಾನ್ಯ ಬಳಕೆಯ ಗುರುತುಗಳಿಗೂ ಶುಲ್ಕ ವಿಧಿಸಬಹುದು.", "ಸಾಮಾನ್ಯ ಬಳಕೆಯನ್ನು ಮೀರಿದ ಹಾನಿಗೆ ಮಾತ್ರ, ರಸೀದಿಗಳ ಆಧಾರದ ಮೇಲೆ ಬಣ್ಣ ಹಚ್ಚುವ ವೆಚ್ಚ ಕಡಿತಗೊಳಿಸಬಹುದು; ಇಲ್ಲದಿದ್ದರೆ ನಿಗದಿತ ಶುಲ್ಕ ಇರಬಾರದು.", "ಸಾಮಾನ್ಯ ಬಳಕೆಯನ್ನು ಮೀರಿದ ದಾಖಲೆಬದ್ಧ ಹಾನಿಗೆ ಮಾತ್ರ ಕಡಿತ ಮಾಡುವಂತೆ, ಸ್ವಯಂಚಾಲಿತ ನಿಗದಿತ ಶುಲ್ಕವಿಲ್ಲದೆ ಬರೆಯಬಹುದೇ?"),
        "hi": ("पेंटिंग की कटौती एक महीने के किराए से अधिक है और सामान्य उपयोग के निशान का खर्च भी आपसे लिया जा सकता है।", "पेंटिंग का खर्च केवल सामान्य घिसावट से अधिक नुकसान के लिए, रसीदों के आधार पर काटा जाए; अन्यथा कोई तय शुल्क न हो।", "क्या पेंटिंग कटौती को सामान्य घिसावट से अधिक दर्ज नुकसान तक सीमित कर सकते हैं, बिना किसी स्वचालित तय शुल्क के?"),
    },
    "MISSING_WITNESS_BLOCK": {
        "en": ("No witness signature section was found. Witnesses help document that the parties signed the agreement.", "Add a witness section with each witness's full name, address, signature and date.", "Could we add a witness section with names, addresses, signatures and date?"),
        "kn": ("ಒಪ್ಪಂದದಲ್ಲಿ ಸಾಕ್ಷಿಗಳ ಸಹಿ ವಿಭಾಗ ಕಾಣುತ್ತಿಲ್ಲ. ಸಾಕ್ಷಿಗಳು ಸಹಿ ಮಾಡಿದುದನ್ನು ದಾಖಲಿಸಲು ಸಹಾಯ ಮಾಡುತ್ತಾರೆ.", "ಪ್ರತಿ ಸಾಕ್ಷಿಯ ಪೂರ್ಣ ಹೆಸರು, ವಿಳಾಸ, ಸಹಿ ಮತ್ತು ದಿನಾಂಕದೊಂದಿಗೆ ಸಾಕ್ಷಿ ವಿಭಾಗ ಸೇರಿಸಿ.", "ಹೆಸರು, ವಿಳಾಸ, ಸಹಿ ಮತ್ತು ದಿನಾಂಕಗಳಿರುವ ಸಾಕ್ಷಿ ವಿಭಾಗ ಸೇರಿಸಬಹುದೇ?"),
        "hi": ("समझौते में गवाहों के हस्ताक्षर का भाग नहीं मिला। गवाह यह दर्ज करने में मदद करते हैं कि पक्षों ने हस्ताक्षर किए।", "हर गवाह का पूरा नाम, पता, हस्ताक्षर और तारीख वाला गवाह अनुभाग जोड़ें।", "क्या नाम, पते, हस्ताक्षर और तारीख वाला गवाह अनुभाग जोड़ सकते हैं?"),
    },
    "MISSING_PROPERTY_ADDRESS": {
        "en": ("The agreement does not clearly identify the rented property. This can cause disputes about what premises are covered.", "Add a property schedule with the complete address, unit number, building name and relevant boundaries.", "Could we attach a complete property schedule and address to the agreement?"),
        "kn": ("ಬಾಡಿಗೆ ಆಸ್ತಿಯನ್ನು ಒಪ್ಪಂದದಲ್ಲಿ ಸ್ಪಷ್ಟವಾಗಿ ಗುರುತಿಸಿಲ್ಲ. ಇದರಿಂದ ಯಾವ ಆಸ್ತಿ ಒಳಗೊಂಡಿದೆ ಎಂಬ ವಿವಾದ ಉಂಟಾಗಬಹುದು.", "ಪೂರ್ಣ ವಿಳಾಸ, ಮನೆ ಅಥವಾ ಫ್ಲಾಟ್ ಸಂಖ್ಯೆ, ಕಟ್ಟಡದ ಹೆಸರು ಮತ್ತು ಗಡಿಗಳಿರುವ ಆಸ್ತಿ ವಿವರ ಸೇರಿಸಿ.", "ಪೂರ್ಣ ಆಸ್ತಿ ವಿವರ ಮತ್ತು ವಿಳಾಸವನ್ನು ಒಪ್ಪಂದಕ್ಕೆ ಸೇರಿಸಬಹುದೇ?"),
        "hi": ("समझौते में किराये की संपत्ति की स्पष्ट पहचान नहीं है। इससे शामिल परिसर को लेकर विवाद हो सकता है।", "पूरा पता, मकान या फ्लैट नंबर, इमारत का नाम और सीमाओं वाला संपत्ति विवरण जोड़ें।", "क्या समझौते में पूरा संपत्ति विवरण और पता जोड़ सकते हैं?"),
    },
    "UNREGISTERED_LONG_LEASE": {
        "en": ("The stated term is at least twelve months, but the document does not mention registration. Long leases generally require registration under Section 17 of the Registration Act, 1908; confirm the applicable requirement locally.", "Have the parties execute and register the lease with the appropriate Sub-Registrar where required, and retain the registration details. Verify any e-Stamp certificate number and status on the official state e-Stamp portal.", "Could we complete any required registration and share the registration and verified e-Stamp details?"),
        "kn": ("ಒಪ್ಪಂದದ ಅವಧಿ ಕನಿಷ್ಠ 12 ತಿಂಗಳು, ಆದರೆ ನೋಂದಣಿ ಉಲ್ಲೇಖವಿಲ್ಲ. Registration Act, 1908ರ Section 17 ಅಡಿಯಲ್ಲಿ ದೀರ್ಘಾವಧಿಯ ಲೀಸ್‌ಗೆ ಸಾಮಾನ್ಯವಾಗಿ ನೋಂದಣಿ ಬೇಕಾಗುತ್ತದೆ; ಸ್ಥಳೀಯ ನಿಯಮವನ್ನು ದೃಢಪಡಿಸಿ.", "ಅಗತ್ಯವಿದ್ದಲ್ಲಿ ಸೂಕ್ತ ಉಪನೋಂದಣಾಧಿಕಾರಿಯ ಬಳಿ ಲೀಸ್‌ಗೆ ಸಹಿ ಮಾಡಿ ನೋಂದಾಯಿಸಿ, ವಿವರಗಳನ್ನು ಉಳಿಸಿ. ಅಧಿಕೃತ ರಾಜ್ಯ ಇ-ಸ್ಟಾಂಪ್ ತಾಣದಲ್ಲಿ ಪ್ರಮಾಣಪತ್ರದ ಸಂಖ್ಯೆ ಮತ್ತು ಸ್ಥಿತಿಯನ್ನು ಪರಿಶೀಲಿಸಿ.", "ಅಗತ್ಯ ನೋಂದಣಿಯನ್ನು ಪೂರ್ಣಗೊಳಿಸಿ, ನೋಂದಣಿ ಮತ್ತು ಪರಿಶೀಲಿಸಿದ ಇ-ಸ್ಟಾಂಪ್ ವಿವರಗಳನ್ನು ಹಂಚಿಕೊಳ್ಳಬಹುದೇ?"),
        "hi": ("समझौते की अवधि कम से कम 12 महीने है, लेकिन दस्तावेज़ में पंजीकरण का उल्लेख नहीं है। Registration Act, 1908 की धारा 17 के तहत लंबी अवधि के पट्टों का सामान्यतः पंजीकरण आवश्यक होता है; स्थानीय आवश्यकता की पुष्टि करें।", "जहाँ आवश्यक हो, उप-पंजीयक के पास पट्टे पर हस्ताक्षर कर पंजीकरण कराएँ और विवरण सुरक्षित रखें। आधिकारिक राज्य ई-स्टाम्प पोर्टल पर प्रमाणपत्र संख्या और स्थिति जाँचें।", "क्या आवश्यक पंजीकरण पूरा करके पंजीकरण और सत्यापित ई-स्टाम्प विवरण साझा कर सकते हैं?"),
    },
    "MISSING_EXECUTION_DATE": {
        "en": ("No clear execution date was found. The date helps establish when the agreement was signed and took effect.", "Add the actual signing date and state separately when the tenancy begins if those dates differ.", "Could we add the signing date and the tenancy start date clearly?"),
        "kn": ("ಒಪ್ಪಂದಕ್ಕೆ ಸಹಿ ಮಾಡಿದ ಸ್ಪಷ್ಟ ದಿನಾಂಕ ಕಾಣುತ್ತಿಲ್ಲ. ಯಾವಾಗ ಸಹಿ ಮಾಡಲಾಯಿತು ಮತ್ತು ಜಾರಿಗೆ ಬಂತು ಎಂಬುದನ್ನು ದಿನಾಂಕ ತಿಳಿಸುತ್ತದೆ.", "ನಿಜವಾದ ಸಹಿ ದಿನಾಂಕವನ್ನು ಸೇರಿಸಿ; ಬಾಡಿಗೆ ಆರಂಭದ ದಿನ ಬೇರೆ ಇದ್ದರೆ ಅದನ್ನೂ ಪ್ರತ್ಯೇಕವಾಗಿ ನಮೂದಿಸಿ.", "ಸಹಿ ದಿನಾಂಕ ಮತ್ತು ಬಾಡಿಗೆ ಆರಂಭದ ದಿನಾಂಕವನ್ನು ಸ್ಪಷ್ಟವಾಗಿ ಸೇರಿಸಬಹುದೇ?"),
        "hi": ("समझौते पर हस्ताक्षर की स्पष्ट तारीख नहीं मिली। तारीख से पता चलता है कि समझौते पर कब हस्ताक्षर हुए और यह कब प्रभावी हुआ।", "वास्तविक हस्ताक्षर की तारीख जोड़ें और किरायेदारी शुरू होने की तारीख अलग हो तो उसे भी लिखें।", "क्या हस्ताक्षर की तारीख और किरायेदारी शुरू होने की तारीख स्पष्ट रूप से जोड़ सकते हैं?"),
    },
}
_TEMPLATES.update({
    "ILLEGAL_COLLATERAL_SMALL_LOAN": {
        "en": ("This clause asks for collateral on a small education loan. Ask the bank to confirm the applicable IBA scheme limit in writing.", "Please remove collateral if the applicable education loan scheme does not require it, or provide the written policy basis and calculation.", "Could you please confirm in writing why collateral is required and whether the IBA education loan threshold applies?"),
        "kn": ("ಈ ಷರತ್ತು ಕಡಿಮೆ ಮೊತ್ತದ ಶಿಕ್ಷಣ ಸಾಲಕ್ಕೆ ಭದ್ರತೆ ಕೇಳುತ್ತದೆ. ಅನ್ವಯಿಸುವ IBA ಯೋಜನೆಯ ಮಿತಿಯನ್ನು ಲಿಖಿತವಾಗಿ ದೃಢೀಕರಿಸಿ.", "ಅನ್ವಯಿಸುವ ಶಿಕ್ಷಣ ಸಾಲ ಯೋಜನೆಯಡಿ ಅಗತ್ಯವಿಲ್ಲದಿದ್ದರೆ ಭದ್ರತೆಯನ್ನು ತೆಗೆದುಹಾಕಿ; ಇಲ್ಲದಿದ್ದರೆ ಲಿಖಿತ ನಿಯಮ ಮತ್ತು ಲೆಕ್ಕವನ್ನು ನೀಡಿ.", "ಈ ಸಾಲಕ್ಕೆ ಭದ್ರತೆ ಏಕೆ ಬೇಕು ಮತ್ತು IBA ಮಿತಿ ಅನ್ವಯವಾಗುತ್ತದೆಯೇ ಎಂದು ಲಿಖಿತವಾಗಿ ತಿಳಿಸುವಿರಾ?"),
        "hi": ("यह शर्त छोटे शिक्षा ऋण पर गिरवी मांगती है। लागू IBA योजना की सीमा लिखित में पूछें।", "यदि लागू शिक्षा ऋण योजना में गिरवी आवश्यक नहीं है तो इसे हटाएँ; अन्यथा लिखित नियम और गणना दें।", "क्या आप लिखित में बता सकते हैं कि गिरवी क्यों जरूरी है और IBA सीमा लागू होती है या नहीं?"),
    },
    "FLOATING_FORECLOSURE_PENALTY": {
        "en": ("This clause appears to charge for early repayment of a floating-rate individual loan. Ask the branch to confirm the applicable RBI rule.", "Please state that no foreclosure or prepayment charge applies where RBI directions prohibit it, and confirm the rate type in writing.", "Could you confirm the floating-rate status and applicable RBI prepayment rule, then revise this clause?"),
        "kn": ("ಫ್ಲೋಟಿಂಗ್ ದರದ ವೈಯಕ್ತಿಕ ಸಾಲವನ್ನು ಮುಂಚಿತವಾಗಿ ತೀರಿಸಿದಾಗ ಈ ಷರತ್ತು ಶುಲ್ಕ ವಿಧಿಸುವಂತೆ ಕಾಣುತ್ತದೆ. ಅನ್ವಯಿಸುವ RBI ನಿಯಮವನ್ನು ದೃಢೀಕರಿಸಿ.", "RBI ನಿರ್ದೇಶನಗಳು ನಿಷೇಧಿಸುವಲ್ಲಿ ಮುಂಗಡ ಪಾವತಿ ಶುಲ್ಕ ಇರುವುದಿಲ್ಲ ಎಂದು ಬರೆದು, ಬಡ್ಡಿದರದ ಪ್ರಕಾರವನ್ನು ದೃಢೀಕರಿಸಿ.", "ಫ್ಲೋಟಿಂಗ್ ದರ ಮತ್ತು ಅನ್ವಯಿಸುವ RBI ನಿಯಮವನ್ನು ದೃಢೀಕರಿಸಿ ಈ ಷರತ್ತನ್ನು ತಿದ್ದುಪಡಿ ಮಾಡುತ್ತೀರಾ?"),
        "hi": ("यह शर्त फ्लोटिंग दर वाले व्यक्तिगत ऋण को समय से पहले चुकाने पर शुल्क लगा सकती है। लागू RBI नियम पूछें।", "जहाँ RBI निर्देश मना करते हैं वहाँ पूर्व भुगतान शुल्क नहीं लगेगा—यह लिखें और दर का प्रकार बताएं।", "क्या आप फ्लोटिंग दर और लागू RBI नियम की पुष्टि करके यह शर्त संशोधित करेंगे?"),
    },
    "UNILATERAL_INTEREST_HIKE": {
        "en": ("This clause may let the bank raise interest or penal charges without written notice to the student or co-borrower.", "Require prior written notice to both the student and co-borrower before any rate or penal charge change takes effect.", "Could we add advance written notice to the student and co-borrower for every rate or penal charge change?"),
        "kn": ("ವಿದ್ಯಾರ್ಥಿ ಅಥವಾ ಸಹ-ಸಾಲಗಾರರಿಗೆ ಲಿಖಿತ ಸೂಚನೆ ನೀಡದೆ ಬಡ್ಡಿ ಅಥವಾ ದಂಡ ಶುಲ್ಕ ಹೆಚ್ಚಿಸಲು ಈ ಷರತ್ತು ಅವಕಾಶ ನೀಡಬಹುದು.", "ಬದಲಾವಣೆ ಜಾರಿಗೆ ಮೊದಲು ವಿದ್ಯಾರ್ಥಿ ಮತ್ತು ಸಹ-ಸಾಲಗಾರರಿಗೆ ಲಿಖಿತ ಮುಂಗಡ ಸೂಚನೆ ಕಡ್ಡಾಯಗೊಳಿಸಿ.", "ಪ್ರತಿ ಬಡ್ಡಿ ಅಥವಾ ದಂಡ ಶುಲ್ಕ ಬದಲಾವಣೆಗೆ ಮುಂಚಿತ ಲಿಖಿತ ಸೂಚನೆ ಸೇರಿಸಬಹುದೇ?"),
        "hi": ("यह शर्त छात्र या सह-उधारकर्ता को लिखित सूचना दिए बिना ब्याज या दंड शुल्क बढ़ाने दे सकती है।", "बदलाव लागू होने से पहले छात्र और सह-उधारकर्ता को लिखित सूचना देना आवश्यक करें।", "क्या हर बदलाव से पहले छात्र और सह-उधारकर्ता को लिखित सूचना जोड़ सकते हैं?"),
    },
    "BLANK_CHEQUE_MANDATE": {
        "en": ("A blank or undated signed cheque could be filled in later without your review.", "Remove the blank-cheque requirement and list any valid repayment mandate and its limits in the signed loan documents.", "Could you replace the blank cheque request with a clearly documented repayment mandate?"),
        "kn": ("ಖಾಲಿ ಅಥವಾ ದಿನಾಂಕವಿಲ್ಲದ ಸಹಿ ಮಾಡಿದ ಚೆಕ್ ಅನ್ನು ನಂತರ ನಿಮ್ಮ ಪರಿಶೀಲನೆಯಿಲ್ಲದೆ ಭರ್ತಿ ಮಾಡಬಹುದು.", "ಖಾಲಿ ಚೆಕ್ ಬೇಡಿಕೆಯನ್ನು ತೆಗೆದುಹಾಕಿ, ಮರುಪಾವತಿ ವಿಧಾನ ಮತ್ತು ಮಿತಿಗಳನ್ನು ಸಹಿ ಮಾಡಿದ ದಾಖಲೆಗಳಲ್ಲಿ ನಮೂದಿಸಿ.", "ಖಾಲಿ ಚೆಕ್ ಬದಲು ಸ್ಪಷ್ಟವಾಗಿ ದಾಖಲಿಸಿದ ಮರುಪಾವತಿ ವಿಧಾನ ಬಳಸಬಹುದೇ?"),
        "hi": ("खाली या बिना तारीख का हस्ताक्षरित चेक बाद में आपकी जानकारी के बिना भरा जा सकता है।", "खाली चेक की मांग हटाएँ और भुगतान आदेश तथा उसकी सीमा हस्ताक्षरित दस्तावेज़ में लिखें।", "क्या खाली चेक की जगह स्पष्ट रूप से दर्ज भुगतान आदेश ले सकते हैं?"),
    },
    "MANDATORY_BUNDLED_INSURANCE": {
        "en": ("This clause appears to require insurance only through the bank's partner. Ask whether cover is optional and whether you may choose another insurer.", "Make insurance optional, permit an insurer of the student's choice, and provide premium and coverage details separately.", "Could you confirm whether this cover is optional and allow us to choose an insurer independently?"),
        "kn": ("ಬ್ಯಾಂಕ್ ಪಾಲುದಾರರಿಂದಲೇ ವಿಮೆ ಖರೀದಿಸಲು ಈ ಷರತ್ತು ಒತ್ತಾಯಿಸುವಂತೆ ಕಾಣುತ್ತದೆ. ಇದು ಐಚ್ಛಿಕವೇ ಮತ್ತು ಬೇರೆ ವಿಮಾದಾರರನ್ನು ಆಯ್ಕೆಮಾಡಬಹುದೇ ಎಂದು ಕೇಳಿ.", "ವಿಮೆಯನ್ನು ಐಚ್ಛಿಕವಾಗಿಡಿ, ವಿದ್ಯಾರ್ಥಿಗೆ ವಿಮಾದಾರರನ್ನು ಆಯ್ಕೆಮಾಡಲು ಅವಕಾಶ ನೀಡಿ ಮತ್ತು ಪ್ರೀಮಿಯಂ ವಿವರಗಳನ್ನು ಪ್ರತ್ಯೇಕವಾಗಿ ನೀಡಿ.", "ವಿಮೆ ಐಚ್ಛಿಕವೇ ಮತ್ತು ನಾವು ಸ್ವತಂತ್ರವಾಗಿ ವಿಮಾದಾರರನ್ನು ಆಯ್ಕೆಮಾಡಬಹುದೇ?"),
        "hi": ("यह शर्त केवल बैंक के साझेदार से बीमा लेने को अनिवार्य करती दिखती है। पूछें कि बीमा वैकल्पिक है या नहीं और क्या दूसरा बीमाकर्ता चुन सकते हैं।", "बीमा वैकल्पिक रखें, छात्र को बीमाकर्ता चुनने दें और प्रीमियम व कवरेज अलग से बताएं।", "क्या यह बीमा वैकल्पिक है और हम स्वतंत्र रूप से बीमाकर्ता चुन सकते हैं?"),
    },
})
_LANGUAGE_CODES = {"en": "en", "kn": "kn", "hi": "hi"}
_GTTS_CODES = {"en": "en", "kn": "kn", "hi": "hi"}


def _optional_translation(clause_text: str, lang: str, fallback: dict[str, str]) -> dict[str, str]:
    """Use a configured provider only for wording; rule decisions stay deterministic."""
    api_key = os.getenv("OPENAI_API_KEY")
    provider = "openai" if api_key else "gemini" if os.getenv("GEMINI_API_KEY") else ""
    if not provider:
        return fallback
    prompt = (
        "Return only a JSON object with string keys explanation, replacement_clause, whatsapp_message. "
        f"Write plain language in language code {lang}. Do not invent legal facts. Clause: {clause_text!r}. "
        f"Use these verified template ideas: {json.dumps(fallback, ensure_ascii=False)}"
    )
    try:
        if provider == "openai":
            body = {"model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"), "messages": [{"role": "user", "content": prompt}], "response_format": {"type": "json_object"}, "temperature": 0}
            request = Request("https://api.openai.com/v1/chat/completions", data=json.dumps(body).encode(), headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
            with urlopen(request, timeout=8) as response:
                result = json.loads(response.read())["choices"][0]["message"]["content"]
        else:
            key = os.environ["GEMINI_API_KEY"]
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
            body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}}
            request = Request(endpoint, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
            with urlopen(request, timeout=8) as response:
                result = json.loads(response.read())["candidates"][0]["content"]["parts"][0]["text"]
        generated = json.loads(result)
        return {key: str(generated[key]) for key in fallback}
    except Exception:
        return fallback


def explain_flagged_clauses(audit: Any, lang: str = "en", generate_audio: bool = True) -> list[dict[str, Any]]:
    """Explain only RED/YELLOW clauses using deterministic offline templates.

    API credentials do not change rule decisions or trigger a model in this
    adapter: all safety-critical wording remains available offline.
    """
    if lang not in _LANGUAGE_CODES:
        raise ValueError("lang must be one of: en, kn, hi")
    results: list[dict[str, Any]] = []
    for clause in audit.clauses:
        if clause.verdict not in {"RED", "YELLOW"}:
            continue
        ids = [rule.rule_id for rule in clause.fired_rules]
        templates = [_TEMPLATES[rule_id] for rule_id in ids if rule_id in _TEMPLATES]
        if not templates:
            continue
        langs: dict[str, dict[str, str]] = {}
        for code in _LANGUAGE_CODES:
            langs[code] = {
                "explanation": " ".join(t[code][0] for t in templates),
                "replacement_clause": " ".join(t[code][1] for t in templates),
                "whatsapp_message": " ".join(t[code][2] for t in templates),
            }
            langs[code] = _optional_translation(clause.clause_text, code, langs[code])
        selected = langs[lang]
        audio_path: str | None = None
        audio_error: str | None = None
        if generate_audio:
            try:
                with tempfile.NamedTemporaryFile(prefix="kararkavach-", suffix=".mp3", delete=False) as audio_file:
                    audio_path = audio_file.name
                gTTS(text=selected["explanation"], lang=_GTTS_CODES[lang]).save(audio_path)
            except Exception as exc:  # gTTS requires a network connection.
                audio_error = f"Audio unavailable: {type(exc).__name__}"
                if audio_path:
                    Path(audio_path).unlink(missing_ok=True)
                    audio_path = None
        results.append({
            "clause_number": clause.clause_number,
            "clause_text": clause.clause_text,
            "verdict": clause.verdict,
            "score": clause.score,
            "rule_ids": ids,
            "legal_references": [r.legal_reference for r in clause.fired_rules if r.legal_reference],
            "languages": langs,
            "explanation": selected["explanation"],
            "replacement_clause": selected["replacement_clause"],
            "whatsapp_message": selected["whatsapp_message"],
            "audio_path": audio_path,
            "audio_error": audio_error,
        })
    return results
