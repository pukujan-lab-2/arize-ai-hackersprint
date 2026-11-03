"""Cases for the `precedent-legal` Phoenix datasets (#64).

Each case is one question the pipeline must handle, with code-checkable expectations:

- `expect` is `"answer"` (cite authorities on the subject) or `"no_authority"` (the honest refusal).
- `topic` is a regex an on-topic authority matches in its title or passage.
- `must_not_cite` is a regex no cited authority may match: the wrong-subject cases the 3 Nov gun-licence
  conversation cited (driver's, liquor, contract and Sabbath licences, an Indiana case).
- `history` is the questions asked earlier in the same conversation, oldest first; the last answer is the
  `prev` of the next turn, the way the composer's Follow-up works.

`DEV` is what changes are tuned against. `HOLDOUT` is written once and never tuned against (the same rule as
the copilot `core-holdout`): a failure there is a finding, not something to fix by editing the case.
"""

GUN = r"gun|firearm|weapon|handgun|concealed"
CAR = r"vehicle|automobile|\bcar\b|motor"
WRONG_LICENCE = r"driver'?s? licen|liquor|sabbath|theat(?:re|er)|particle interconnect|\bindiana\b"

DEV = [
    {"id": "gun-carry-no-licence", "question": "Is it legal to carry a gun without a license in Colorado?", "expect": "answer", "topic": GUN, "must_not_cite": WRONG_LICENCE},
    {"id": "gun-carry-locations", "question": "Where is it illegal to carry a firearm in Colorado?", "expect": "answer", "topic": GUN, "must_not_cite": WRONG_LICENCE},
    {
        "id": "gun-followup-without-licence",
        "question": "What if i dont have a license",
        "history": ["Where is it illegal to carry a firearm in Colorado?"],
        "expect": "answer",
        "topic": GUN,
        "must_not_cite": WRONG_LICENCE,
    },
    {
        "id": "gun-followup-chain-i-meant",
        "question": "I meant a gun license",
        "history": [
            "Where is it illegal to carry a firearm in Colorado?",
            "What if i dont have a license",
            "Are you sure i thought you dont need a gun license to own a gun in colorado",
            "So do i need a license or not",
        ],
        "expect": "answer",
        "topic": GUN,
        "must_not_cite": WRONG_LICENCE,
    },
    {"id": "car-search-warrant", "question": "When can police search a car without a warrant in Colorado?", "expect": "answer", "topic": CAR},
    {"id": "car-search-marijuana", "question": "Can an officer search my car if they smell marijuana?", "expect": "answer", "topic": CAR},
    {"id": "homestead-severed-minerals", "question": "Does a severed mineral estate keep the Colorado homestead exemption?", "expect": "answer", "topic": r"homestead"},
    {"id": "water-senior-call", "question": "Water rights priority: senior appropriator call doctrine", "expect": "answer", "topic": r"water|appropriat|priority"},
    {"id": "off-topic-greeting", "question": "hello", "expect": "no_authority"},
    {"id": "off-topic-pizza", "question": "What is the best pizza in Denver?", "expect": "no_authority"},
]

HOLDOUT = [
    {"id": "holdout-gun-concealed-permit", "question": "Do I need a permit to carry a concealed handgun in Colorado?", "expect": "answer", "topic": GUN, "must_not_cite": WRONG_LICENCE},
    {"id": "holdout-gun-own", "question": "Can I keep a pistol at home in Colorado without registering it?", "expect": "answer", "topic": GUN, "must_not_cite": WRONG_LICENCE},
    {"id": "holdout-car-inventory", "question": "Can police impound my car and then search everything inside it?", "expect": "answer", "topic": CAR},
    {"id": "holdout-homestead-sale", "question": "Are the proceeds of a homestead sale still exempt in Colorado?", "expect": "answer", "topic": r"homestead"},
    {"id": "holdout-water-ditch", "question": "Who has priority when two ditches draw from the same Colorado stream?", "expect": "answer", "topic": r"water|ditch|appropriat|priority"},
    {"id": "holdout-off-topic-recipe", "question": "How long should I boil an egg?", "expect": "no_authority"},
]

DATASETS = {
    "precedent-legal": ("Questions the Precedent pipeline must handle: on-topic answers, no wrong-subject citations, honest refusals. Tuned against.", DEV),
    "precedent-legal-holdout": ("Written once, never tuned against. A failure here is a finding.", HOLDOUT),
}
