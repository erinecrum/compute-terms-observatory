# `governs` backfill: drafts for review

**Status: drafts only. Nothing is committed to registry.yaml.**

These are scaffolding. The judgment is yours: edit this file directly and tell me to
apply it, or tell me the changes and I will make them.

Each line becomes a required `governs:` field on its document, answering: *what does
this document govern, and why is that this entry's tracked artifact?*

109 documents, generated from 20 patterns. Review the patterns first;
the per-document table below differs only in the names.

## Patterns

| entry class | doc type | n | pattern |
|---|---|---|---|
| hosted | `ai_documentation` | 6 | The documentation Anthropic publishes for the models served by the Claude API, describing the service this entry tracks. |
| hosted | `aup` | 4 | The acceptable-use restrictions Anthropic imposes on customers of the Claude hosted model API, forming part of the terms governing the service this entry tracks. |
| hosted | `deprecation` | 2 | The policy Anthropic publishes on retiring and pinning model versions in the Claude API, governing continuity for the service this entry tracks. |
| hosted | `dpa` | 4 | The data-processing terms OpenAI offers customers of the OpenAI API / GPT hosted model API; they govern its processing of customer personal data in the service this entry tracks. |
| hosted | `privacy_policy` | 8 | How Anthropic handles personal data of users of the Claude hosted service, which is the relationship this entry tracks. |
| hosted | `service_terms` | 9 | The contract between Anthropic and a customer of the Claude hosted model API; it is the master agreement for the service this entry tracks. |
| hosted | `subprocessor_list` | 5 | The sub-processors Anthropic engages to deliver the Claude hosted model API, disclosed under the data-processing terms for the service this entry tracks. |
| hosted | `transparency_report` | 2 | How Anthropic responds to government and law-enforcement requests for data held in the Claude hosted service, which is the relationship this entry tracks. |
| infrastructure | `ai_documentation` | 3 | The documentation Amazon Web Services publishes for its AI and ML services, describing part of the compute service this entry tracks. |
| infrastructure | `ai_terms` | 3 | Service-specific terms Amazon Web Services applies to its AI and ML offerings, supplementing the master agreement for the compute service this entry tracks. |
| infrastructure | `aup` | 4 | The acceptable-use restrictions Amazon Web Services imposes on customers of its compute service, forming part of the terms governing the service this entry tracks. |
| infrastructure | `dpa` | 9 | The data-processing terms Amazon Web Services offers customers of its compute service; they govern its processing of customer personal data in the service this entry tracks. |
| infrastructure | `privacy_policy` | 10 | How Amazon Web Services handles personal data of users of its compute service, which is the relationship this entry tracks. |
| infrastructure | `service_terms` | 11 | The contract between Amazon Web Services and a customer of its compute service; it is the master agreement for the service this entry tracks. |
| infrastructure | `sla` | 4 | The availability and service-credit commitment Amazon Web Services makes for its compute service, governing the service this entry tracks. |
| infrastructure | `subprocessor_list` | 6 | The sub-processors Amazon Web Services engages to deliver its compute service, disclosed under the data-processing terms for the service this entry tracks. |
| infrastructure | `transparency_report` | 2 | How Microsoft Azure responds to government and law-enforcement requests for customer data held in its compute service, which is the relationship this entry tracks. |
| weights | `ai_documentation` | 8 | The model card OpenAI publishes in the repository that distributes the gpt-oss weights; it is the publisher's own documentation of the artifact this entry tracks. |
| weights | `aup` | 1 | The use policy Meta attaches to the Llama weights; it restricts what a downloader may do with them, so it attaches to the artifact this entry tracks rather than to any hosted service. |
| weights | `model_license` | 8 | The licence OpenAI attaches to the gpt-oss weights; it is the instrument under which a downloader may use, modify and redistribute them, so it governs the artifact this entry tracks. |

*(shown with the first entry's names substituted)*

## All 109 documents

| # | provider | doc type | document | draft `governs` line |
|---|---|---|---|---|
| 1 | claude | `ai_documentation` | Anthropic model cards / Transparency Hub | The documentation Anthropic publishes for the models served by the Claude API, describing the service this entry tracks. |
| 2 | claude | `aup` | Anthropic Usage Policy | The acceptable-use restrictions Anthropic imposes on customers of the Claude hosted model API, forming part of the terms governing the service this entry tracks. |
| 3 | claude | `deprecation` | Anthropic model deprecations | The policy Anthropic publishes on retiring and pinning model versions in the Claude API, governing continuity for the service this entry tracks. |
| 4 | claude | `privacy_policy` | Anthropic Privacy Policy | How Anthropic handles personal data of users of the Claude hosted service, which is the relationship this entry tracks. |
| 5 | claude | `service_terms` | Anthropic Commercial Terms of Service | The contract between Anthropic and a customer of the Claude hosted model API; it is the master agreement for the service this entry tracks. |
| 6 | claude | `subprocessor_list` | Anthropic Sub-processors | The sub-processors Anthropic engages to deliver the Claude hosted model API, disclosed under the data-processing terms for the service this entry tracks. |
| 7 | claude | `transparency_report` | Anthropic Transparency Hub | How Anthropic responds to government and law-enforcement requests for data held in the Claude hosted service, which is the relationship this entry tracks. |
| 8 | command | `ai_documentation` | Cohere Enterprise Data Commitments | The documentation Cohere publishes for the models served by the Command API, describing the service this entry tracks. |
| 9 | command | `privacy_policy` | Cohere Privacy Policy | How Cohere handles personal data of users of the Command hosted service, which is the relationship this entry tracks. |
| 10 | command | `service_terms` | Cohere Terms of Use | The contract between Cohere and a customer of the Command hosted model API; it is the master agreement for the service this entry tracks. |
| 11 | command | `subprocessor_list` | Cohere Sub-processors (Trust Center) | The sub-processors Cohere engages to deliver the Command hosted model API, disclosed under the data-processing terms for the service this entry tracks. |
| 12 | deepseek-platform | `privacy_policy` | DeepSeek Privacy Policy | How DeepSeek handles personal data of users of the DeepSeek platform hosted service, which is the relationship this entry tracks. |
| 13 | deepseek-platform | `service_terms` | DeepSeek Open Platform Terms of Service | The contract between DeepSeek and a customer of the DeepSeek platform hosted model API; it is the master agreement for the service this entry tracks. |
| 14 | gemini | `ai_documentation` | Google Generative AI Prohibited Use Policy + model | The documentation Google publishes for the models served by the Gemini API, describing the service this entry tracks. |
| 15 | gemini | `aup` | Google Generative AI Prohibited Use Policy | The acceptable-use restrictions Google imposes on customers of the Gemini hosted model API, forming part of the terms governing the service this entry tracks. |
| 16 | gemini | `dpa` | Google Cloud Data Processing Addendum (Gemini) | The data-processing terms Google offers customers of the Gemini hosted model API; they govern its processing of customer personal data in the service this entry tracks. |
| 17 | gemini | `privacy_policy` | Gemini API Additional Terms | How Google handles personal data of users of the Gemini hosted service, which is the relationship this entry tracks. |
| 18 | gemini | `service_terms` | Gemini API Additional Terms of Service | The contract between Google and a customer of the Gemini hosted model API; it is the master agreement for the service this entry tracks. |
| 19 | gemini | `subprocessor_list` | Google Cloud Third Party Subprocessors (Gemini) | The sub-processors Google engages to deliver the Gemini hosted model API, disclosed under the data-processing terms for the service this entry tracks. |
| 20 | gemini | `transparency_report` | Google Transparency Report (enterprise) | How Google responds to government and law-enforcement requests for data held in the Gemini hosted service, which is the relationship this entry tracks. |
| 21 | grok | `aup` | xAI Acceptable Use Policy | The acceptable-use restrictions xAI imposes on customers of the Grok hosted model API, forming part of the terms governing the service this entry tracks. |
| 22 | grok | `dpa` | xAI Data Processing Addendum | The data-processing terms xAI offers customers of the Grok hosted model API; they govern its processing of customer personal data in the service this entry tracks. |
| 23 | grok | `privacy_policy` | xAI Privacy Policy | How xAI handles personal data of users of the Grok hosted service, which is the relationship this entry tracks. |
| 24 | grok | `service_terms` | xAI Terms of Service | The contract between xAI and a customer of the Grok hosted model API; it is the master agreement for the service this entry tracks. |
| 25 | mistral-platform | `ai_documentation` | Mistral usage policy / model cards | The documentation Mistral publishes for the models served by the Mistral platform API, describing the service this entry tracks. |
| 26 | mistral-platform | `dpa` | Mistral AI Data Processing Addendum | The data-processing terms Mistral offers customers of the Mistral platform hosted model API; they govern its processing of customer personal data in the service this entry tracks. |
| 27 | mistral-platform | `privacy_policy` | Mistral AI Privacy Policy | How Mistral handles personal data of users of the Mistral platform hosted service, which is the relationship this entry tracks. |
| 28 | mistral-platform | `service_terms` | Mistral AI Terms of Service | The contract between Mistral and a customer of the Mistral platform hosted model API; it is the master agreement for the service this entry tracks. |
| 29 | mistral-platform | `subprocessor_list` | Mistral AI Sub-processors | The sub-processors Mistral engages to deliver the Mistral platform hosted model API, disclosed under the data-processing terms for the service this entry tracks. |
| 30 | moonshot-platform | `ai_documentation` | Kimi OpenPlatform Terms of Service | The documentation Moonshot AI publishes for the models served by the Moonshot platform API, describing the service this entry tracks. |
| 31 | moonshot-platform | `privacy_policy` | Moonshot (Kimi) Platform privacy policy | How Moonshot AI handles personal data of users of the Moonshot platform hosted service, which is the relationship this entry tracks. |
| 32 | moonshot-platform | `service_terms` | Moonshot (Kimi) Platform model-use agreement | The contract between Moonshot AI and a customer of the Moonshot platform hosted model API; it is the master agreement for the service this entry tracks. |
| 33 | openai | `ai_documentation` | OpenAI usage policies & system cards | The documentation OpenAI publishes for the models served by the OpenAI API / GPT API, describing the service this entry tracks. |
| 34 | openai | `aup` | OpenAI Usage Policies | The acceptable-use restrictions OpenAI imposes on customers of the OpenAI API / GPT hosted model API, forming part of the terms governing the service this entry tracks. |
| 35 | openai | `deprecation` | OpenAI deprecations | The policy OpenAI publishes on retiring and pinning model versions in the OpenAI API / GPT API, governing continuity for the service this entry tracks. |
| 36 | openai | `dpa` | OpenAI Data Processing Addendum | The data-processing terms OpenAI offers customers of the OpenAI API / GPT hosted model API; they govern its processing of customer personal data in the service this entry tracks. |
| 37 | openai | `privacy_policy` | OpenAI Privacy Policy | How OpenAI handles personal data of users of the OpenAI API / GPT hosted service, which is the relationship this entry tracks. |
| 38 | openai | `service_terms` | OpenAI Service Terms | The contract between OpenAI and a customer of the OpenAI API / GPT hosted model API; it is the master agreement for the service this entry tracks. |
| 39 | openai | `service_terms` | OpenAI Business Terms | The contract between OpenAI and a customer of the OpenAI API / GPT hosted model API; it is the master agreement for the service this entry tracks. |
| 40 | openai | `subprocessor_list` | OpenAI Sub-processor List | The sub-processors OpenAI engages to deliver the OpenAI API / GPT hosted model API, disclosed under the data-processing terms for the service this entry tracks. |
| 41 | aws | `ai_documentation` | AWS AI Service Cards | The documentation Amazon Web Services publishes for its AI and ML services, describing part of the compute service this entry tracks. |
| 42 | aws | `ai_terms` | AWS Responsible AI Policy | Service-specific terms Amazon Web Services applies to its AI and ML offerings, supplementing the master agreement for the compute service this entry tracks. |
| 43 | aws | `aup` | AWS Acceptable Use Policy | The acceptable-use restrictions Amazon Web Services imposes on customers of its compute service, forming part of the terms governing the service this entry tracks. |
| 44 | aws | `dpa` | AWS GDPR Center (DPA) | The data-processing terms Amazon Web Services offers customers of its compute service; they govern its processing of customer personal data in the service this entry tracks. |
| 45 | aws | `privacy_policy` | AWS Privacy Notice | How Amazon Web Services handles personal data of users of its compute service, which is the relationship this entry tracks. |
| 46 | aws | `service_terms` | AWS Customer Agreement | The contract between Amazon Web Services and a customer of its compute service; it is the master agreement for the service this entry tracks. |
| 47 | aws | `service_terms` | AWS Service Terms | The contract between Amazon Web Services and a customer of its compute service; it is the master agreement for the service this entry tracks. |
| 48 | aws | `sla` | Amazon Compute Service Level Agreement (EC2/ECS/Fa | The availability and service-credit commitment Amazon Web Services makes for its compute service, governing the service this entry tracks. |
| 49 | aws | `subprocessor_list` | AWS Sub-processors | The sub-processors Amazon Web Services engages to deliver its compute service, disclosed under the data-processing terms for the service this entry tracks. |
| 50 | azure | `ai_documentation` | Microsoft Responsible AI / Transparency Notes | The documentation Microsoft Azure publishes for its AI and ML services, describing part of the compute service this entry tracks. |
| 51 | azure | `ai_terms` | Microsoft Product Terms for Online Services | Service-specific terms Microsoft Azure applies to its AI and ML offerings, supplementing the master agreement for the compute service this entry tracks. |
| 52 | azure | `aup` | Microsoft Acceptable Use Policy (Online Services) | The acceptable-use restrictions Microsoft Azure imposes on customers of its compute service, forming part of the terms governing the service this entry tracks. |
| 53 | azure | `dpa` | Microsoft Products and Services Data Protection Ad | The data-processing terms Microsoft Azure offers customers of its compute service; they govern its processing of customer personal data in the service this entry tracks. |
| 54 | azure | `privacy_policy` | Microsoft Privacy Statement | How Microsoft Azure handles personal data of users of its compute service, which is the relationship this entry tracks. |
| 55 | azure | `service_terms` | Microsoft Customer Agreement (published) | The contract between Microsoft Azure and a customer of its compute service; it is the master agreement for the service this entry tracks. |
| 56 | azure | `sla` | SLA for Microsoft Online Services (consolidated; i | The availability and service-credit commitment Microsoft Azure makes for its compute service, governing the service this entry tracks. |
| 57 | azure | `subprocessor_list` | Microsoft Online Services Subprocessor List | The sub-processors Microsoft Azure engages to deliver its compute service, disclosed under the data-processing terms for the service this entry tracks. |
| 58 | azure | `transparency_report` | Microsoft Law Enforcement Requests Report | How Microsoft Azure responds to government and law-enforcement requests for customer data held in its compute service, which is the relationship this entry tracks. |
| 59 | baseten | `dpa` | Baseten Data Processing Addendum | The data-processing terms Baseten offers customers of its compute service; they govern its processing of customer personal data in the service this entry tracks. |
| 60 | baseten | `privacy_policy` | Baseten Privacy Policy | How Baseten handles personal data of users of its compute service, which is the relationship this entry tracks. |
| 61 | baseten | `service_terms` | Baseten Terms and Conditions | The contract between Baseten and a customer of its compute service; it is the master agreement for the service this entry tracks. |
| 62 | baseten | `sla` | Baseten Service Level Agreement | The availability and service-credit commitment Baseten makes for its compute service, governing the service this entry tracks. |
| 63 | baseten | `subprocessor_list` | Baseten Sub-processors (Trust Center) | The sub-processors Baseten engages to deliver its compute service, disclosed under the data-processing terms for the service this entry tracks. |
| 64 | coreweave | `aup` | CoreWeave Acceptable Use Policy | The acceptable-use restrictions CoreWeave imposes on customers of its compute service, forming part of the terms governing the service this entry tracks. |
| 65 | coreweave | `dpa` | CoreWeave Data Processing Agreement | The data-processing terms CoreWeave offers customers of its compute service; they govern its processing of customer personal data in the service this entry tracks. |
| 66 | coreweave | `privacy_policy` | CoreWeave Privacy Policy | How CoreWeave handles personal data of users of its compute service, which is the relationship this entry tracks. |
| 67 | coreweave | `service_terms` | CoreWeave Terms of Use | The contract between CoreWeave and a customer of its compute service; it is the master agreement for the service this entry tracks. |
| 68 | coreweave | `subprocessor_list` | CoreWeave Sub-processors | The sub-processors CoreWeave engages to deliver its compute service, disclosed under the data-processing terms for the service this entry tracks. |
| 69 | crusoe | `dpa` | Crusoe Data Processing and Security Terms | The data-processing terms Crusoe offers customers of its compute service; they govern its processing of customer personal data in the service this entry tracks. |
| 70 | crusoe | `privacy_policy` | Crusoe Privacy Notice | How Crusoe handles personal data of users of its compute service, which is the relationship this entry tracks. |
| 71 | crusoe | `service_terms` | Crusoe Legal Center (Cloud Platform Terms of Servi | The contract between Crusoe and a customer of its compute service; it is the master agreement for the service this entry tracks. |
| 72 | crusoe | `subprocessor_list` | Crusoe Cloud Subprocessors | The sub-processors Crusoe engages to deliver its compute service, disclosed under the data-processing terms for the service this entry tracks. |
| 73 | gcp | `ai_documentation` | Google Generative AI Prohibited Use Policy | The documentation Google Cloud publishes for its AI and ML services, describing part of the compute service this entry tracks. |
| 74 | gcp | `ai_terms` | Google Cloud Service Specific Terms (AI/ML data us | Service-specific terms Google Cloud applies to its AI and ML offerings, supplementing the master agreement for the compute service this entry tracks. |
| 75 | gcp | `aup` | Google Cloud Platform Acceptable Use Policy | The acceptable-use restrictions Google Cloud imposes on customers of its compute service, forming part of the terms governing the service this entry tracks. |
| 76 | gcp | `dpa` | Cloud Data Processing Addendum (CDPA) | The data-processing terms Google Cloud offers customers of its compute service; they govern its processing of customer personal data in the service this entry tracks. |
| 77 | gcp | `privacy_policy` | Google Cloud Privacy Notice | How Google Cloud handles personal data of users of its compute service, which is the relationship this entry tracks. |
| 78 | gcp | `service_terms` | Google Cloud Platform Terms of Service | The contract between Google Cloud and a customer of its compute service; it is the master agreement for the service this entry tracks. |
| 79 | gcp | `sla` | Compute Engine Service Level Agreement | The availability and service-credit commitment Google Cloud makes for its compute service, governing the service this entry tracks. |
| 80 | gcp | `subprocessor_list` | Google Cloud Third Party Subprocessors | The sub-processors Google Cloud engages to deliver its compute service, disclosed under the data-processing terms for the service this entry tracks. |
| 81 | gcp | `transparency_report` | Google Cloud Transparency & Data Protection | How Google Cloud responds to government and law-enforcement requests for customer data held in its compute service, which is the relationship this entry tracks. |
| 82 | lambda | `privacy_policy` | Lambda Privacy Policy | How Lambda handles personal data of users of its compute service, which is the relationship this entry tracks. |
| 83 | lambda | `service_terms` | Lambda Terms of Service | The contract between Lambda and a customer of its compute service; it is the master agreement for the service this entry tracks. |
| 84 | runpod | `dpa` | Runpod Data Processing Agreement | The data-processing terms Runpod offers customers of its compute service; they govern its processing of customer personal data in the service this entry tracks. |
| 85 | runpod | `privacy_policy` | Runpod Privacy Policy | How Runpod handles personal data of users of its compute service, which is the relationship this entry tracks. |
| 86 | runpod | `service_terms` | Runpod Terms of Service | The contract between Runpod and a customer of its compute service; it is the master agreement for the service this entry tracks. |
| 87 | together | `dpa` | Together AI Data Processing Addendum | The data-processing terms Together AI offers customers of its compute service; they govern its processing of customer personal data in the service this entry tracks. |
| 88 | together | `privacy_policy` | Together AI Privacy Policy | How Together AI handles personal data of users of its compute service, which is the relationship this entry tracks. |
| 89 | together | `service_terms` | Together AI Terms of Service | The contract between Together AI and a customer of its compute service; it is the master agreement for the service this entry tracks. |
| 90 | vast | `dpa` | Vast.ai Data Processing Agreement | The data-processing terms Vast.ai offers customers of its compute service; they govern its processing of customer personal data in the service this entry tracks. |
| 91 | vast | `privacy_policy` | Vast.ai Privacy Policy | How Vast.ai handles personal data of users of its compute service, which is the relationship this entry tracks. |
| 92 | vast | `service_terms` | Vast.ai Terms of Service | The contract between Vast.ai and a customer of its compute service; it is the master agreement for the service this entry tracks. |
| 93 | deepseek | `ai_documentation` | Model card / usage policy | The model card DeepSeek publishes in the repository that distributes the DeepSeek open models weights; it is the publisher's own documentation of the artifact this entry tracks. |
| 94 | deepseek | `model_license` | DeepSeek-R1 model license (MIT) | The licence DeepSeek attaches to the DeepSeek open models weights; it is the instrument under which a downloader may use, modify and redistribute them, so it governs the artifact this entry tracks. |
| 95 | gemma | `ai_documentation` | Model card / usage policy | The model card Google publishes in the repository that distributes the Gemma weights; it is the publisher's own documentation of the artifact this entry tracks. |
| 96 | gemma | `model_license` | Gemma Terms of Use (Gemma license) | The licence Google attaches to the Gemma weights; it is the instrument under which a downloader may use, modify and redistribute them, so it governs the artifact this entry tracks. |
| 97 | glm | `ai_documentation` | GLM-5.2 model card | The model card Z.ai publishes in the repository that distributes the GLM weights; it is the publisher's own documentation of the artifact this entry tracks. |
| 98 | glm | `model_license` | GLM-5.2 model license (MIT) | The licence Z.ai attaches to the GLM weights; it is the instrument under which a downloader may use, modify and redistribute them, so it governs the artifact this entry tracks. |
| 99 | gpt-oss | `ai_documentation` | Model card / usage policy | The model card OpenAI publishes in the repository that distributes the gpt-oss weights; it is the publisher's own documentation of the artifact this entry tracks. |
| 100 | gpt-oss | `model_license` | gpt-oss model license (Apache 2.0) | The licence OpenAI attaches to the gpt-oss weights; it is the instrument under which a downloader may use, modify and redistribute them, so it governs the artifact this entry tracks. |
| 101 | kimi | `ai_documentation` | Kimi K2 model card | The model card Moonshot AI publishes in the repository that distributes the Kimi open models weights; it is the publisher's own documentation of the artifact this entry tracks. |
| 102 | kimi | `model_license` | Kimi K2 model license (Modified MIT) | The licence Moonshot AI attaches to the Kimi open models weights; it is the instrument under which a downloader may use, modify and redistribute them, so it governs the artifact this entry tracks. |
| 103 | llama | `aup` | Llama 4 Acceptable Use Policy | The use policy Meta attaches to the Llama weights; it restricts what a downloader may do with them, so it attaches to the artifact this entry tracks rather than to any hosted service. |
| 104 | llama | `model_license` | Llama 4 Community License | The licence Meta attaches to the Llama weights; it is the instrument under which a downloader may use, modify and redistribute them, so it governs the artifact this entry tracks. |
| 105 | minimax | `ai_documentation` | MiniMax-M3 model card | The model card MiniMax publishes in the repository that distributes the MiniMax weights; it is the publisher's own documentation of the artifact this entry tracks. |
| 106 | minimax | `model_license` | MiniMax-M3 model license (MiniMax Community Licens | The licence MiniMax attaches to the MiniMax weights; it is the instrument under which a downloader may use, modify and redistribute them, so it governs the artifact this entry tracks. |
| 107 | mistral-open | `ai_documentation` | Model card / usage policy | The model card Mistral publishes in the repository that distributes the Mistral open models weights; it is the publisher's own documentation of the artifact this entry tracks. |
| 108 | qwen | `ai_documentation` | Model card / usage policy | The model card Alibaba publishes in the repository that distributes the Qwen weights; it is the publisher's own documentation of the artifact this entry tracks. |
| 109 | qwen | `model_license` | Qwen3-235B-A22B model license (Apache-2.0) | The licence Alibaba attaches to the Qwen weights; it is the instrument under which a downloader may use, modify and redistribute them, so it governs the artifact this entry tracks. |
