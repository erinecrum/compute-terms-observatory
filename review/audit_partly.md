# Audit triage: the `partly` verdicts, with document quotes

From the full 107-document pass, 2026-07-20. These are documents that cover the
tracked artifact alongside other things. Usually fine, per your read.

Each entry shows the document's OWN scope sentence where it declares one.

## aws / `ai_terms` — partly/high
**AWS Responsible AI Policy**  
<https://aws.amazon.com/ai/responsible-ai/policy/>

- **Scope clause:** _(declares no scope sentence)_
- **Basis:** This policy governs use of AWS AI/ML Services (features, functionality, and third-party models), so it binds a compute service that runs customer workloads only insofar as that compute is used for AI/ML workloads, not the general-purpose compute service in its entirety.
- **Objection:** The policy scopes itself explicitly to 'artificial intelligence and machine learning Services, features, and functionality (including third-party models)'—a general compute service that runs arbitrary customer workloads is not inherently an AI/ML Service, so for the bulk of non-AI compute use this policy is silent and the governing terms are the referenced AUP and Service Terms instead; however, this objection is only partial because a compute service that runs AI/ML workloads clearly falls within scope, making 'partly' the honest answer rather than 'no'.

## azure / `privacy_policy` — yes/medium
**Microsoft Privacy Statement**  
<https://privacy.microsoft.com/en-us/privacystatement>

- **Scope clause:** _(declares no scope sentence)_
- **Basis:** The Microsoft Privacy Statement expressly applies to Microsoft services and servers, including enterprise and developer products, and governs how personal data is processed when customers use those products—which includes an Azure compute service that runs customer workloads.
- **Objection:** The registry's defect pattern is a privacy policy filed against something with which the reader has no data-processing relationship; one could argue a compute service that merely runs customer workloads is governed instead by the Azure enterprise/product terms and Data Protection Addendum rather than a consumer-facing privacy statement. But this objection is genuinely weak here: unlike downloaded model weights (which create no ongoing relationship with the publisher), a hosted compute service is an operated service where Microsoft does process data, and the statement explicitly extends to enterprise and developer products and services and directs organizational users to relevant sections—so a data-processing relationship plainly exists.

## baseten / `privacy_policy` — partly/medium
**Baseten Privacy Policy**  
<https://www.baseten.co/privacy-policy/>

- **Scope clause:** _(declares no scope sentence)_
- **Basis:** This privacy policy governs Baseten's handling of personal data collected through its Website and Service, which is a genuine Baseten instrument; the entry tracks the compute service that runs customer workloads, and the privacy policy does bind users of that Service with respect to their personal data, though its stated scope centers on Website/Service usage data rather than the mechanics of running workloads.
- **Objection:** The document defines 'Service' as 'the Website' and 'Website' as BaseTen at baseten.co, so on its own text its scope is website-visitor data collection (email, name, usage/cookie data), not the operation of the compute platform that executes customer workloads; the artifact tracked is an infrastructure compute service, and this policy never addresses processing of the customer workloads or data run through that infrastructure, so it arguably governs the marketing/account website rather than the compute artifact itself. That objection is real but not fatal: users of the compute service create accounts and are bound by this policy as to their own personal data, so it partially governs the artifact rather than being an entirely misfiled document like the reseller-ToS-as-model-card case.

## claude / `transparency_report` — partly/medium
**Anthropic Transparency Hub**  
<https://www.anthropic.com/transparency>

- **Scope clause:** _(declares no scope sentence)_
- **Basis:** This is Anthropic's transparency/model report describing Claude models including their capabilities, safeguards, and access surfaces (Anthropic API, Bedrock, Vertex, Azure), so it does describe the hosted model service this entry tracks, but it is a disclosure/reporting instrument rather than a binding governance document, and it governs the models generally rather than the API service specifically.
- **Objection:** A transparency report is not a governing instrument at all: it discloses how models behave and what safeguards exist, but it does not bind a reader or set terms of use for reaching the model over an API (that role belongs to a Usage Policy or Terms of Service, which this document merely links to); on this view it governs nothing and merely reports, so it fails to 'govern' the hosted API artifact even though it is squarely on-topic and correctly published by Anthropic about the right family of products.

## gcp / `transparency_report` — partly/medium
**Google Cloud Transparency & Data Protection**  
<https://cloud.google.com/transparency>

- **Scope clause:** _(declares no scope sentence)_
- **Basis:** This transparency/data-protection overview describes Google Cloud's data-handling commitments and government-request practices that apply across Google Cloud services, including a compute service that runs customer workloads, but it is a general trust-principles document rather than the binding terms specific to any one compute service.
- **Objection:** The document is a marketing-style transparency overview that points to other instruments (the CDPA, privacy commitments, whitepapers) for the actual binding terms and never names or scopes itself to a specific compute service, so one could argue it governs nothing operationally and merely summarizes commitments; however this objection is only moderately strong because the artifact is a Google Cloud service and the document expressly states data-protection commitments that apply 'when you use Google Cloud,' which squarely covers such a service.

## gemini / `ai_documentation` — yes/medium
**Google Generative AI Prohibited Use Policy + model cards**  
<https://policies.google.com/terms/generative-ai>

- **Scope clause:** _(declares no scope sentence)_
- **Basis:** These are Google's terms of service governing use of Google's Generative AI Services reached as hosted offerings, which is the artifact this entry tracks (the gemini hosted model service reached over an API); the referenced Prohibited Use Policy and model cards bind a reader's use of that service.
- **Objection:** The document header states these Generative AI Additional Terms no longer apply as of May 22, 2024 (superseded by the main Google Terms of Service unless you're a signed business partner), so this specific instrument may no longer bind current users of the hosted API; additionally the text is generic ToS language and never names Gemini or an API surface directly, so its coverage of this exact artifact is inferred rather than explicit—though this objection is moderate rather than decisive because the terms clearly do govern Google's Generative AI Services of which the gemini hosted service is one, and the entry bundles the Prohibited Use Policy and model cards which remain operative.

## grok / `service_terms` — partly/medium
**xAI Terms of Service**  
<https://x.ai/legal/terms-of-service>

- **Scope clause:** These Terms of Service (“Terms”) apply to your or others’ access, interactions and/or use of Grok, Grokipedia, and xAI’s other services for individuals, including associated applications, features, tools, software and websites (collectively, the “Service”).
- **Basis:** This is xAI's consumer Terms of Service governing individual use of Grok and other consumer-facing services, but it explicitly carves out API and developer/business use as governed by the separate Enterprise Terms of Service; since the entry tracks a hosted model service reached over an API, this consumer document only partially covers the artifact and points elsewhere for the API access itself.
- **Objection:** The document repeatedly and explicitly states that 'Our Enterprise Terms of Service govern the use of our Services for developers and businesses, including xAI APIs,' which directly excludes the very access mode this entry tracks (a hosted model reached over an API); read strictly by scope, the correct governing instrument is the Enterprise Terms, not this consumer document, so one could argue it does not govern the tracked artifact at all — though this is weaker than the two named defects because it is the same publisher's own product family and the consumer Terms still govern non-API consumer access to the same Grok service.

## lambda / `service_terms` — partly/high
**Lambda Terms of Service**  
<https://lambda.ai/legal/terms-of-service>

- **Scope clause:** these Terms, our Privacy Policy governs how Lambda collects, stores, and protects your information when you use the Services.
- **Basis:** This document is Lambda's Website Terms of Use governing use of the Lambda Sites, and it explicitly defers to the separate Cloud Terms of Service for any Lambda API key and cloud offerings; the tracked artifact is a compute service that runs customer workloads, which this instrument covers only partially (account creation, general use) while routing the core compute usage to the Cloud Terms.
- **Objection:** One could argue this document does NOT govern the compute service at all, since it self-describes as 'Website Terms of Use' governing the Sites (including Lambda Chat) and expressly states that the Cloud Terms of Service govern Lambda API keys and other cloud offerings that run workloads; on that reading the compute service is governed by a different instrument entirely. This objection is real but not fully decisive, because the page is titled 'Terms of Service' aggregating multiple documents, and the Website Terms still bind the Customer's account and general Service use in ways that partly touch the compute relationship.

## mistral-open / `ai_documentation` — partly/medium
**Model card / usage policy**  
<https://legal.mistral.ai/terms>

- **Scope clause:** _(declares no scope sentence)_
- **Basis:** This is a legal-documents hub from the same publisher that includes a License Notice and Usage Policy, which do govern use of downloadable open weights, but the page itself is an index spanning many instruments (consumer ToS, DPA, connector terms) most of which do not bind a reader of downloaded weights.
- **Objection:** The document is labeled a 'Model card / usage policy' but the actual text is a table-of-contents landing page that governs nothing on its own; it merely links to separate instruments, and it never states any binding terms for the mistral-open weights, so as filed it does not itself govern the tracked artifact and is arguably a mis-tracked URL that should point to the specific License Notice or the weights' own license.

## mistral-platform / `ai_documentation` — partly/medium
**Mistral usage policy / model cards**  
<https://mistral.ai/terms/>

- **Scope clause:** _(declares no scope sentence)_
- **Basis:** This is a hub page indexing Mistral's legal documents, several of which (Commercial Terms of Service, Usage Policy, Privacy Policy) do govern use of Mistral's hosted API service, so it governs the tracked artifact in part while also covering many unrelated products and audiences.
- **Objection:** The document itself is only a directory/overview that binds no one to anything—it defers all actual governing terms to linked instruments, and its named type ('model cards') and the specific hosted-API artifact are not the subject of this page at all; a reader seeking the terms binding an API-reached hosted service must click through to the Commercial Terms of Service, so this landing page arguably governs nothing directly. That objection is real but not fatal, because the page's enumerated scope clearly encompasses the hosted service among its subjects, unlike a genuine mismatch such as a reseller's ToS masquerading as a model card.

## together / `dpa` — partly/medium
**Together AI Data Processing Addendum**  
<https://www.together.ai/privacy>

- **Scope clause:** This Policy applies to Personal Data that the Company collects, uses, and discloses and which may include: (i) data collected through the Services, (ii) data collected through Professional Support, (iii) data collected through the Website, and (iv) data collected from third-party sources.
- **Basis:** This is Together Computer's Privacy Policy governing personal data collected through 'the Services,' which it defines to include the programmatic APIs and interfaces that host and run AI models; a compute service that runs customer workloads falls within that scope insofar as the policy governs data processing arising from customers using those Services.
- **Objection:** The document is labeled a Privacy Policy (not a DPA as the entry claims) and its scope is data-collection practices for individuals interacting with the Website and Services, not the operational terms, SLAs, or governing agreement of a compute service that runs customer workloads; a privacy policy tells users what personal data the company collects about them, whereas the artifact tracked is an infrastructure/compute offering whose actual governing instrument would be terms of service or a genuine data processing addendum, so the fit is partial and the entry's 'dpa' type label is a mismatch with the actual document.

## vast / `privacy_policy` — yes/medium
**Vast.ai Privacy Policy**  
<https://vast.ai/privacy>

- **Scope clause:** _(declares no scope sentence)_
- **Basis:** This privacy policy governs data collection practices of Vast.ai's website and services, which is the platform through which customers access the compute service that runs their workloads, so it applies to the tracked infrastructure artifact.
- **Objection:** The document repeatedly and narrowly defines its scope as the 'Website' (https://vast.ai, media channels, mobile app) and describes browser cookies, web beacons, and marketing emails—consumer web-tracking concerns—not the compute execution service itself; one could argue running customer workloads on rented GPUs is governed by a terms-of-service or DPA rather than this website privacy policy, and the mismatch here echoes the described defect where a privacy policy is filed against something it does not actually govern. However, this objection is weakened because the compute service is delivered through and inseparable from the Website/platform the policy explicitly covers, and the header even labels it a 'Data Processing Agreement,' so the policy does bind the reader with respect to the pl

