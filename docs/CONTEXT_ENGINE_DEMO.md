Context Engine Demo (Tactus)
============================

This walkthrough shows how to exercise the recursive Context engine against a real
WikiText2 corpus, including compaction, expansion, and explicit message control.

Run
---

```bash
conda run -n py311 --no-capture-output python scripts/demo_context_engine.py
```

Example output (abridged)
-------------------------

```
Context Engine Demo (Tactus)
============================
Wikitext2 cache: /Users/ryan.porter/Projects/Tactus/tests/fixtures/wikitext-2-raw-v1

Corpus snapshot
===============
1. = Valkyria Chronicles III =
2. Senjo no Valkyria 3 : Unrecorded Chronicles ( Japanese : ... )
3. The game began development in 2010 , carrying over a large portion of the work done on Valkyria Chronicles II . While it retained the sta...
4. It met with positive sales in Japan , and was praised by both Japanese and western critics . After release , it received downloadable con...
5. = = Gameplay = =

Direct retrieval
================
Evidence count: 2
- train-1: Concept work for Valkyria Chronicles III began after development finished on Valkyria Chronicles II in early 2010 , with full development beginning shortly a...
- train-2: The majority of material created for previous games , such as the BLiTZ system and the design of maps , was carried over . Alongside this , improvements were...

Dual concept retrieval (full corpus)
====================================
Query (gaming): Valkyria Chronicles III
- train-1: Concept work for Valkyria Chronicles III began after development finished on Valkyria Chronicles II in early 2010 , with full development...
Query (geopolitics): United States
- train-1: " Crazy in Love " was released to radio in the United States on May 18 , 2003 under formats including Rhythmic , Top 40 , and Urban radio...

Default context (logical structure)
===================================
- system("You are a support agent.")
- context(wikitext_search)
- history()
- user("<none>")

Context pack output (wikitext_search)
=====================================
1. Concept work for Valkyria Chronicles III began after development finished on Valkyria Chronicles II in early 2010 , with full development beginning shortly a...
2. The majority of material created for previous games , such as the BLiTZ system and the design of maps , was carried over . Alongside this , improvements were...

Default context assembly (rendered)
===================================
Context: default_context
Token estimate: 51
System prompt:
You are a support agent.

Concept work for Valkyria Chronicles III began after development finished on Valkyria Chronicles II in early 2010 , with full development beginning shortly after this . The director of Valkyria Chronicles II , Takeshi Ozawa , returned to that role for Valkyria Chronicles III . Develop...

Default context (message list, hierarchical)
===========================================
messages
└─ system
   ├─ context
   │  └─ system: Concept work for Valkyria Chronicles III began after development finished on Valkyria Chronicles II in early 2010 , with full development beginning shortly a...
   └─ system: You are a support agent.

Default context (message list, flattened)
=========================================
- system: You are a support agent.

Explicit context with history (logical structure)
=================================================
- system("You are a researcher.")
- context(wikitext_search)
- history()
- user("Summarize the evidence.")

Context pack output (wikitext_search)
=====================================
1. Concept work for Valkyria Chronicles III began after development finished on Valkyria Chronicles II in early 2010 , with full development beginning shortly a...
2. The majority of material created for previous games , such as the BLiTZ system and the design of maps , was carried over . Alongside this , improvements were...

Explicit context assembly (rendered)
====================================
Context: explicit_context
Token estimate: 63
System prompt:
You are a researcher.

Concept work for Valkyria Chronicles III began after development finished on Valkyria Chronicles II in early 2010 , with full development beginning shortly after this . The director of Valkyria Chronicles II , Takeshi Ozawa , returned to that role for Valkyria Chronicles III . Develop...
History:
- user: What is Valkyria Chronicles?
- assistant: It is a tactical RPG series.
User message:
Summarize the evidence.

Explicit context with history (message list, hierarchical)
=========================================================
messages
└─ system
   ├─ context
   │  └─ system: Concept work for Valkyria Chronicles III began after development finished on Valkyria Chronicles II in early 2010 , with full development beginning shortly a...
   └─ system: You are a researcher.
└─ history
   └─ user: What is Valkyria Chronicles?
   └─ assistant: It is a tactical RPG series.
└─ user: Summarize the evidence.

Explicit context with history (message list, flattened)
======================================================
- system: You are a researcher.
- user: What is Valkyria Chronicles?
- assistant: It is a tactical RPG series.
- user: Summarize the evidence.

Expansion and pagination (logical structure)
=============================================
- system("Evidence:")
- context(paged_retriever)
- user("Give highlights.")

Pagination requests
===================
Offsets requested: [0, 1, 2]
Each offset is a paginated request for more evidence.

Context pack pages (paged_retriever)
====================================
- offset 0: A lookout aboard Weehawken spotted Atlanta at 04 : 10 on the morning of 17 June . When the latter ship closed to within about 1 @.@ 5 miles ( 2 @.@ 4 km ) of the two Union ships...
- offset 1: A lookout aboard Weehawken spotted Atlanta at 04 : 10 on the morning of 17 June . When the latter ship closed to within about 1 @.@ 5 miles ( 2 @.@ 4 km ) of the two Union ships...
- offset 2: A lookout aboard Weehawken spotted Atlanta at 04 : 10 on the morning of 17 June . When the latter ship closed to within about 1 @.@ 5 miles ( 2 @.@ 4 km ) of the two Union ships...

Expansion context assembly (rendered)
=====================================
Context: expanding_context
Token estimate: 365
System prompt:
Evidence:

A lookout aboard Weehawken spotted Atlanta at 04 : 10 on the morning of 17 June . When the latter ship closed to within about 1 @.@ 5 miles ( 2 @.@ 4 km ) of the two Union ships , she fired one round from her bow gun that passed over Weehawken and landed near Nahant . Shortly afterward , Atlanta ran aground on a sandbar ; she was briefly able to free herself , but the pressure of the...
User message:
Give highlights.

Expansion context (message list, hierarchical)
==============================================
messages
└─ system
   ├─ context
   │  └─ system: A lookout aboard Weehawken spotted Atlanta at 04 : 10 on the morning of 17 June . When the latter ship closed to within about 1 @.@ 5 miles ( 2 @.@ 4 km ) of...
   │  └─ system: On 23 May 1915 , between two and four hours after news of the Italian declaration of war reached the main Austro @-@ Hungarian naval base at Pola , Zrínyi an...
   │  └─ system: At the halfway point of the season , with the Blue Jackets barely into double digit wins with an 11 – 25 – 5 record , worst in the league , and sitting 20 po...
   └─ system: Evidence:
└─ user: Give highlights.

Expansion context (message list, flattened)
===========================================
- system: Evidence:
- user: Give highlights.

Regeneration and compaction (logical structure)
===============================================
- system("Evidence: Please summarize the evidence with precision.")
- context(wikitext_search)
- user("Summarize quickly and focus on the key facts.")

Compaction attempts
===================
Pack budgets: [80, 20]
Each budget is the maximum characters allowed for the pack on that attempt.

Compaction pack snapshots (wikitext_search)
===========================================
- budget 80: Concept work for...
- budget 20: Concept work for...

Compaction context assembly (rendered)
======================================
Context: compact_context
Token estimate: 18
System prompt:
Evidence: Please summarize the evidence with precision.

Concept work for...
User message:
Summarize quickly and focus on the key facts.

Compaction context (message list, hierarchical)
==============================================
messages
└─ system
   ├─ context
   │  └─ system: Concept work for...
   │  └─ system: Concept work for...
   └─ system: Evidence: Please summarize the evidence with precision.
└─ user: Summarize quickly and focus on the key facts.

Compaction context (message list, flattened)
============================================
- system: Evidence: Please summarize the evidence with precision.
- user: Summarize quickly and focus on the key facts.
```

Notes
-----

- The output is abridged to keep the demo readable.
- The full output is reproducible by running the script above.
- Standard notation:
  - "logical structure" shows the intended Context plan (system/context/history/user).
  - "rendered" shows the actual message list sent to the model after assembly.
  - "Context pack output" shows the retriever output before it is inserted into the context.
  - "Offsets requested" lists pagination offsets sent to the retriever.
  - "Pack budgets" lists the maximum character budgets used during compaction attempts.
