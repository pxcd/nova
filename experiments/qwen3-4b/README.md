# Qwen3 4B provider checks

LM Studio reported `qwen/qwen3-4b-2507` loaded at 4-bit quantization. The separate HA agent uses the existing LM Studio connection, NOVA's current instructions/tools, three prior exchanges and parallel tool calls disabled. Its Assist pipeline is **Qwen3 4B**. NOVA's configured webapp pipeline remains GPT-OSS until deliberately changed.

Seven nonexecuting cases passed: spoken year, original-version follow-up, explicit episode, Netflix/HBO/Prime restart flags, and ordinary Prime resume without a restart flag. Most direct warmed routing requests were 0.6–1.0 seconds; the first observed request was 4.6 seconds, and the follow-up needed two model calls totalling 2.0 seconds. These are single observations, not a controlled comparison or TTFT benchmark. Simulated catalog results were supplied for search-first plans; no TV actions executed. A real HA streaming greeting with its actual tool set also succeeded in 3.7 seconds.

Apple FM's live HA provider and pipeline were removed at the user's request, and the optional compatibility bridge was stopped. Historical FM source/test artifacts remain under version control; they are not on NOVA's active inference path. The user's standalone `fm serve` terminal is separate from the removed HA configuration.
