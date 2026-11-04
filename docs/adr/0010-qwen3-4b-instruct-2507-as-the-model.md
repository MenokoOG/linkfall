# 0010: Qwen3-4B-Instruct-2507 as the model

Date: 2026-11-04 · Status: Proposed

## Context

LINKFALL runs offline on an Asus Vivobook (i5-1235U, no GPU) with WSL capped at 12 GB (11 GiB visible). Lawrence's constraints are open source and no vendor lock-in, and he chose to use available models, not train one.

We measured three small instruct models on 2026-11-04 with llama.cpp build b12110, Q4_K_M, 6 threads. `llama-bench` (600-token prompt, 140-token output):

| Model | Prompt tok/s | Output tok/s | Peak RSS |
|---|---|---|---|
| LFM2.5-1.2B | 79.5 | 28.9 | 1.3 GB |
| Llama-3.2-3B | 26.4 | 10.1 | 3.5 GB |
| Qwen3-4B-Instruct-2507 | 21.1 | 8.5 | 4.4 GB |

Licenses came from the Hugging Face model cards and were not read in full: Qwen Apache-2.0, Llama `llama3.2`, LFM "other". Phi-4-mini-instruct (MIT on its card) was not benchmarked. Lawrence picked Qwen.

A second pass ran Qwen through `llama-server` with a Tactical prompt of about 380 tokens, 8 prompts in free-JSON mode and 8 in `json_schema` mode, temperature 0. At 6 threads the median call took 8.8 s (first call 21 s), the prompt cache supplied a median of 321 prompt tokens, 8 of 8 outputs matched the schema in both modes, and 7 of 8 obeyed the game rules. Server peak RSS was 4.8 GB. At 12 threads two calls took 104 s and 118 s.

## Decision

We will use **Qwen3-4B-Instruct-2507**, quantized Q4_K_M, served by llama.cpp.

- **Weights:** `unsloth/Qwen3-4B-Instruct-2507-GGUF`, file `Qwen3-4B-Instruct-2507-Q4_K_M.gguf`, SHA-256 `3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597` (verified after download), Hugging Face repo revision `a06e946bb6b655725eafa393f4a9745d460374c9` as of 2026-11-04. `scripts/fetch_model.sh` downloads by revision and refuses a mismatch.
- **Runtime:** llama.cpp release b12110, the Ubuntu x64 tarball, SHA-256 `368227edcc229be5f9bed16a2223d79b5e41d0ac2e19bcf5825e82291c060e55`, built into `Dockerfile.model` with the hash checked. The `latest` release tag pointed at a stub release with one asset on that date, so we pin the build number.
- **Settings:** `--threads 6`, context 4096, one slot. The thread count is pinned in `compose.yaml` and checked by the benchmark script. The default of all threads was about 12 times slower in our test.
- **Structured output:** request `json_schema` response format and validate anyway (ADR 0003, 0005). Validation is the control. The constrained mode is a convenience.
- **Swap:** any OpenAI-compatible server and any GGUF fit behind `ModelClient`. A swap needs a new run of the benchmark and the eval set, and a new ADR.
- **Memory ceiling:** the `model` container gets a 6 GB limit. Measured peak is 4.8 GB.

**OWASP Top 10 for LLM Applications 2025:**
- LLM03 supply chain: the weights are third-party and the GGUF is a conversion by unsloth, not Qwen. The SHA-256 and revision pin detect change after our test. They can't show that the conversion is faithful to Qwen's official weights. Residual risk is on record. The model container has no internet route (ADR 0004), and the validator and engine bound what a bad model can do.
- LLM04 data and model poisoning: we don't train or fine-tune. A poisoned upstream model could still bias proposals. The same bounds apply, and the red-team replays run on every model change.
- LLM10 unbounded consumption: token cap per call, timeout 45 s proposed (about 5 times the median), one slot, 6 GB limit.
- LLM02, 07, 08, 09 stay N/A as in ADR 0002.

## Alternatives considered

- **LFM2.5-1.2B.** Fastest and smallest. Rejected because the license reads "other" and we haven't read it, and Lawrence wants a plainly free license. Revisit if its license is clear and quality tests pass.
- **Llama-3.2-3B.** Rejected for the Llama license terms, which we haven't read in full, and for being no faster than Qwen in our test. Revisit never.
- **Phi-4-mini-instruct (MIT).** Not benchmarked. Considered because of the MIT license. Rejected by Lawrence's choice. Revisit if Qwen's quality or license disappoints.
- **Convert the GGUF ourselves from Qwen's official weights.** Considered to shorten the supply chain. Rejected for now because of the extra tooling and time. Revisit before any hosted release.
- **A model trained for LINKFALL.** Rejected by Lawrence on 2026-11-04.
- **A hosted API such as Jev.** Rejected as the default (offline requirement). It may arrive later as an optional adapter, off by default.

## Consequences

- Pro: free license, fits the memory cap, about 9 s per call at 6 threads, constrained JSON works.
- Pro: the pins make the setup reproducible and the swap path is clear.
- Con: a turn with three model calls costs about 27 s (computed from the medians, not measured on a full turn). Mitigation: ADR 0008 streams cards.
- Con: evidence is thin. The first pass used 8 prompts per mode, one template, temperature 0, Tactical only. A second pass on 2026-11-04 ran the real agents: 6 Tactical states (6 of 6 schema-valid, 4 of 6 rule-valid), 3 Comms states (quiet, forged order, truce offer: each read correctly), 1 selector call, and two full five-turn missions (15 calls each, median 7.8 s, max 12.3 s, about 24 s per turn, prompts of 356 tokens with 307 served from cache). That is still a handful of samples at temperature 0. Mitigation: the model evals in ADR 0007 run before M1 closes.
- Con: Qwen's replies use long dashes in flavor text. That is model output, not LINKFALL copy, and we leave it.
- Undo: easy. `ModelClient` and the compose file isolate the model.

## Related

0002 (engine owns state), 0003 (supervisor and `ModelClient`), 0004 (containers), 0005 (agent contract), 0007 (evals), 0008 (UI).
