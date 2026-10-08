# Related work

InquestBench is a small synthetic evaluation toolkit. Replaying an incident, fixing inputs, and measuring tool use are established practices. This comparison uses the projects' primary repositories and papers, reviewed on 8 October 2026; it is not a leaderboard or an exhaustive survey.

| Project | Relevant contribution | Implication for Inquest |
|---|---|---|
| [Cloud-OpsBench](https://github.com/LLM4Ops/Cloud-OpsBench) ([paper](https://arxiv.org/abs/2603.00468)) | Deterministic Kubernetes incident snapshots, cached investigation tools, and process-level evaluation across two systems | Replayability and investigation efficiency alone are not differentiators. Its current repository reports 754 cases and 57 fault types; Inquest's 120 cases are only smoke fixtures. |
| [OpenRCA](https://github.com/microsoft/OpenRCA) | Operational telemetry from Telecom, Bank, and Market systems, with root-cause evaluation and an agent baseline | Synthetic signal recognition needs validation against incidents authored independently of the generator. |
| [AIOpsLab](https://github.com/microsoft/AIOpsLab) | Microservice deployments, workloads, fault injection, telemetry, and agent interaction for detection through mitigation | A saved synthetic bundle cannot establish the operational realism of live service interactions. |
| [ITBench](https://github.com/itbench-hub/ITBench) ([paper](https://arxiv.org/abs/2502.05352)) | Enterprise IT automation tasks spanning SRE, security/compliance, and financial operations | Inquest deliberately covers a much narrower diagnosis contract; it does not evaluate full IT operations. |
| [ORCA-bench](https://github.com/ORCA-bench/ORCA-bench) ([paper](https://arxiv.org/abs/2607.28545)) | Oncall agent evaluation using incidents and telemetry from an instrumented OpenTelemetry demonstration system | Realistic oncall investigation is a separate validation target from solving Inquest's fixed signatures. |
| [OpenRCA 2.0](https://arxiv.org/abs/2606.27154) | Step-wise causal process annotations constructed from fault interventions and checked propagation | A correct final label or a relevant service citation is weaker evidence than a supported causal explanation. |

## Questions Inquest can investigate

These are proposed experiments, not implemented advantages:

1. Does expected information gain select more useful probes than random or downstream-alert policies under identical tool budgets?
2. Does separating telemetry interpretation from belief updates reduce failures, and where does that separation introduce errors?
3. How well do reported probabilities predict accepted diagnoses on independently authored cases? Does dev-only calibration help?

A comparison must document equal knowledge and budgets, fitting data, prompts, model identity, data checksums, and code revision. It must retain malformed outputs, exceptions, and failed investigations. Success versus budget and actual model usage should accompany aggregate accuracy.

## Evidence still missing

The public repository contains no autonomous-agent result table. Its handcrafted grading demonstrations and tests validate interfaces, not investigation performance. Independent authored cases and a real-model pilot are the next research priorities. Generated-set success, even if near-perfect, would support only a narrow claim about that generator. Broader claims require operational datasets or environments and a compatible evaluation protocol.

No cross-project performance claim is made: fault coverage, telemetry, agent knowledge, answer contracts, and resource budgets differ.
