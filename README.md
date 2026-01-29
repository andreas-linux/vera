By Andreas Hamberger, M.A. Phil in Logic (Humboldt University). 

30 January 2026

linux@linux.co.nz

Following on from a popular article series of mine, we are now unveiling Verified Existence and Reason Architecture (V.E.R.A).

To paraphrase a real legend: Do you pine for the nice days of an AI not fooling you, or endangering your enterprise in production? Then this post might be just for you :-)

"I've been working on a free version of an engine to make AI actually intelligent. It has finally reached the stage where it's even usable (though may not be depending on what you want), and I am willing to put out the sources for wider distribution."

Artificial vs. Actual
We are currently in an arms race to make AI sound more convincing. We build massive Retrieval-Augmented Generation (RAG) pipelines to feed models better context, hoping that if we stuff enough text into the prompt, the machine will stop hallucinating. However, RAG is just a search engine attached to a probabilistic guess. It simulates knowing, but it does not know. It remains artificial.

V.E.R.A. is not an RAG.

V.E.R.A. - Verified Existence Reason Architecture - does not just retrieve text; it verifies reality using the strict rules of Non-Traditional Predication Theory (NTP). It forces the system to mathematically distinguish between describing a concept and asserting its existence. 

The proposition of this project is simple but radical: If we can successfully implement the logical system laid out here, enforcing the absolute separation of Predication ($ℳ$) and Existence ($E!$), we will stop generating probable tokens and start deriving verified truths.

We will not just enhance artificial intelligence. We will create real intelligence.

Precision Gap

Minimize image
Edit image
Delete image

Add a caption (optional)
We are living through a renaissance of artificial intelligence. Every day, large language models (LLMs) demonstrate feats of creativity that were unimaginable a decade ago. They write code, compose poetry and summarise vast corpuses of text. But ask an enterprise architect about deploying these models into a mission-critical environment, where legal liability or human safety is on the line, and the enthusiasm cools.

Why? Because of all their brilliance, LLMs are fundamentally probabilistic engines. They predict the next likely token, not the truth. They do not know what exists; they only know what words tend to appear near other words. In the industry, we politely call their error hallucinations. In formal logic, we call them ontological errors.

When an AI tells a user that a specific legal precedent exists when it doesn’t, or invents a chemical compound that violates the laws of physics, it isn’t lying in the human sense. It is conflating predication (describing properties) with existence (asserting reality).

Today, I am announcing V.E.R.A. Verified Existence Reason Architecture, an open-source project designed to close this gap. V.E.R.A. is not a new LLM; it is a logic engine that wraps around LLMs to provide deterministic source-validated reasoning. It is the bridge between the fluid creativity of generative AI and the rigid epistemic precision required by enterprise architecture.

The Humboldt Connection: Why 1990s Logic Solves 2020s Problems

Minimize image
Edit image
Delete image

Add a caption (optional)
The theoretical foundation of the V.E.R.A. was laid long before the invention of Transformer architecture. In the early 1990s, I was a researcher at Humboldt University in Berlin, working under Professor Horst Wessel.

(A necessary historical note: My professor, a rigorous man of science and logic, shared a name with a notorious historical figure from the Nazi era. They are, of course, entirely different people. The logic we developed was the antithesis of ideology; it was about the mathematical purity of truth.)

Wessel and his colleagues, including K.-H. Krampitz, developed the Non-Traditional Predication Theory (NTP). At the time, it was a solution to paradoxes in classical logic. Today, I realised it is the missing blueprint for trustworthy AI.

The core insight of NTP is simple yet radical: Predication ($ℳ$) must be strictly separated from Existence ($E!$).

In classical logic (and in standard LLM behaviour), saying that all swans are white implies that swans exist. The NTP rejects this. It allows us to process the sentence All unicorns have horns as a valid predicative statement ($ℳ$) while simultaneously affirming that unicorns do not exist ($~E!$).

V.E.R.A. operationalises this theory. It creates a system that can reason about concepts without hallucinating their existence.

The V.E.R.A. Project charter
Minimize image
Edit image
Delete image

Add a caption (optional)
This article serves as the official project charter for V.E.R.A. We are building this as an open-source initiative because the problem of AI reliability is too large, and too important to be solved behind closed doors. I am writing this from an Enterprise Architecture standpoint so that we can all take this model and logic system and implement it in our companies and agencies to secure LLMs and anchor them in guardrails and existing reality.

1. The mission

Minimize image
Edit image
Delete image

Add a caption (optional)
To build an AI architecture that never claims to exist without evidence. V.E.R.A. aims to provide a Logical Integrity Layer that can be integrated with any LLM (Claude, GPT, and Llama) to audit its outputs for ontological validity.

2. Architectural Principles

Minimize image
Edit image
Delete image

Add a caption (optional)
Our architecture is governed by principles derived from Wessel’s work and validated against his 1992 primary source material:

Principle 1: The Wall of Separation The system shall maintain an absolute logical firewall between Predication (what things are like) and Existence (that things are). The former is a linguistic function, and the latter is an empirical claim requiring evidence.

Principle 2: Evidence-based Existence. The system utilises a curated $E!$ knowledge base (starting with verified datasets like Wikidata/Wikipedia). No entity is granted the status of existing unless it can be found in this corpus.

Principle 3: Fail-Safe Refusal If a user asks a question that requires an existence claim for a non-existent entity (e.g., What is the mass of the tooth fairy?), V.E.R.A. does not hallucinate weight. It triggers a logic gate that refuses the premise, citing the lack of verified evidence.

The technology: How V.E.R.A. Works
Minimize image
Edit image
Delete image

Add a caption (optional)
V.E.R.A. is not prompt engineering. It is a structured information system designed according to TOGAF standards. It operates through a triple-layer verification service:

Layer 1: The Krampitz Load Analyzer

Named after the logician K.-H. Krampitz, this service analyzes every statement to determine its Existential Loading ($e$ or $n$).

Loaded ($e$): The Apple iPhone 15 costs $999. (Presupposes iPhones exist.)

Not loaded ($n$): If unicorns existed, they would have horns. (A logical definition, not a claim of reality.)

Most AI errors occur because systems treat $n$-type statements as if they are $e$-type facts. V.E.R.A. mathematically distinguishes them using validated rules (R1–R9).

Layer 2: The E! Verification service

When an LLM generates a claim, like Professor Smith published a paper in 2024, V.E.R.A. pauses. It extracts the subject (Professor Smith) and queries the $E!$ corpus.

Status: $E!$ (Exists): The system proceeds.

Status: $sim E!$ (does not exist): The system flags the statement. It forces the output to qualify as hypothetical or reject it entirely.

Layer 3: Contextual Identity (The D-Service)Standard AI struggles with identity; it assumes that if two things look alike, they are the same. V.E.R.A. Uses Indiscernibility Relations ($D1–D4$) to handle nuance. It can distinguish between the following:

Weak Indiscernibility ($D2$): Two things look the same (e.g., a deep fake and a real photo).

Strong Indiscernibility ($D4$): Two things are the same (verified by provenance).

This allows V.E.R.A. to solve complex logical traps, like Poincaré’s Paradox, that confuse standard vector-based models .

The business case for V.E.R.A.
Minimize image
Edit image
Delete image

Add a caption (optional)
Why does this matter to the enterprise?

1. Auditability compliance

In regulated industries (Finance, Healthcare, and Government), you cannot rely on a black box neural network. You need a reasoning chain. V.E.R.A. provides a step-by-step audit trail: We asserted X because Rule R1 was satisfied by Evidence Y in the corpus.

2. Stopping the Hallucination Loop

By verifying existence before predication, we cut off the root source of the hallucination. The system simply cannot invent a person or an event because the $E!$ check will fail before the sentence is completed. Custom business rules and requirements and documents can be loaded up into the Corpus and provide the basis of profound business rules-based guard rails.

3. Vibe Coding with Safety Rails

We are entering an era of vibe coding and rapid prototyping where AI writes the software. This is powerful but risky. V.E.R.A. acts as the structural engineer for the code the AI writes, ensuring that the logical foundations are sound even if the generation is rapid.

Roadmap: Where We Are Going
We follow the TOGAF Architecture Development Method (ADM).

Business Requirements:

Phase A (Architecture Vision):

Phase B (Business Architecture):

Phase C (Information Systems Architecture):

Phase D (Technology Architecture):



Core code and all documents are available now.

Join the Movement, the V.E.R.A. Manifesto
V.E.R.A. is an ambitious attempt to marry the rigour of German complex logic with the agility of modern software engineering. It is a project for those who believe that truth is a feature, not an option.

We are looking for contributors:

Logicians to help refine the hexadecagon structure.

Python Developers to Help Build the Krampitz Load Analyzer and the E! Verification service.

Data architects to assist with the Wikipedia and other integrations for the $E!$ Corpus.

Evangelists to help spread the word that V.E.R.A. has arrived, and the age of the Stochastic Parrot is ending. The age of Verified Reason is beginning.

