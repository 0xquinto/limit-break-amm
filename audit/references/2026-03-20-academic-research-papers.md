# Academic Research Papers: DeFi/AMM Security (2025-2026)

Research compiled 2026-03-20 for Limit Break AMM audit framework.

---

## 1. Automated DeFi Exploit Detection

### 1a. DeFiTail: DeFi Protocol Inspection through Cross-Contract Execution Analysis
- **Authors**: Xiaoqi Li, Wenkai Li, Zhiquan Liu, Yuqing Zhang, Yingjie Mao
- **Date**: November 2025
- **URL**: https://arxiv.org/abs/2511.00408
- **Published**: IEEE (also at arXiv:2511.00408)
- **Summary**: First framework using deep learning for access control and flash loan exploit detection by feeding cross-contract static data flow analysis. Achieves 98.39% accuracy on access control exploits and 97.43% on flash loan exploits, plus 86.67% on malicious contract detection from CVE dataset. Key insight: victim-only analysis misses attacker interaction logic; cross-contract data flow is essential for detecting composability exploits.

### 1b. Comprehensive Review of Smart Contract and DeFi Security: Attack, Vulnerability Detection, and Automated Repair
- **Date**: June 2025
- **URL**: https://www.sciencedirect.com/science/article/abs/pii/S0957417425020500
- **Published**: Expert Systems with Applications
- **Summary**: Comprehensive survey covering attack vectors, vulnerability detection methods, and automated repair. Documents that DeFi has suffered $77.1B in total losses (per REKT Database 2023) with only $6.5B recovered. Provides taxonomy of detection approaches including static analysis, symbolic execution, fuzzing, and ML-based methods.

### 1c. LookAhead: Preventing DeFi Attacks via Unveiling Adversarial Contracts
- **Authors**: Shoupeng Ren, Lipeng He, Tianyu Tu, Di Wu, Jian Liu, Kui Ren, Chun Chen
- **Date**: 2025 (FSE 2025)
- **URL**: https://arxiv.org/abs/2401.07261
- **Published**: ACM FSE 2025
- **Summary**: ML-based framework that detects DeFi attacks by classifying adversarial contracts *before* they execute, rather than detecting attack transactions. Uses Pruned Semantic-Control Flow Tokenization (PSCFT) to represent smart contract programs. Achieves F1-score of 0.8966, a 44.4% improvement over prior state-of-the-art, with only 0.16% false positive rate. Key insight: with private mempools, transaction-level detection is insufficient; contract-level classification is needed.

### 1d. An Automated Vulnerability Detection Framework for Smart Contracts
- **Date**: 2025
- **URL**: https://dl.acm.org/doi/10.1145/3705616
- **Published**: ACM Distributed Ledger Technologies: Research and Practice
- **Summary**: Automated framework for smart contract vulnerability detection integrating multiple analysis techniques. Addresses the challenge of scaling vulnerability detection across the growing number of deployed contracts.

---

## 2. AMM-Specific Vulnerability Patterns

### 2a. Automated Attack Synthesis for Constant Product Market Makers (CPMM-Exploiter)
- **Date**: April 2024 (updated 2025)
- **URL**: https://arxiv.org/abs/2404.05297
- **Summary**: Grammar-based fuzzer that automatically detects and generates end-to-end exploits for CPMM composability bugs. Documents 23 exploits since 2022 causing $2.2M in losses from token-AMM composability issues alone. Achieves recall of 0.91 and 0.89 on two real-world exploit datasets vs. maximum 0.36/0.58 for five baselines. Generated 18 new exploits on live Ethereum/BSC worth $12.9K. Key insight: composability bugs between non-standard token contracts and CPMMs are a systematic, underexplored vulnerability class.

### 2b. am-AMM: An Auction-Managed Automated Market Maker
- **Date**: 2025
- **URL**: https://arxiv.org/abs/2403.03367
- **Published**: Springer
- **Summary**: Proposes auction-managed AMM to address loss-versus-rebalancing (LVR) through censorship-resistant onchain auctions. Key insight: MEV extraction from AMMs is a fundamental design problem, not just an implementation bug; protocol-level mechanism design changes are needed.

### 2c. AMM Taxonomy and Archetypes
- **Date**: Updated 2025
- **URL**: https://arxiv.org/html/2309.12818v3
- **Summary**: Comprehensive taxonomy of AMM designs covering security properties. Non-incorporative AMMs depending on external price sources are susceptible to manipulated feeds, update delays, and high-volatility inaccuracies. AMMs relying on external liquidity providers are vulnerable to liquidity shortfalls during volatility.

---

## 3. Price Manipulation Detection

### 3a. AiRacleX: Automated Detection of Price Oracle Manipulations via LLM-Driven Knowledge Mining and Prompt Generation
- **Date**: February 2025
- **URL**: https://arxiv.org/abs/2502.06348
- **Published**: IEEE (also at arXiv:2502.06348)
- **Summary**: Three-LLM pipeline for oracle manipulation detection. LLM-1 extracts domain knowledge from academic papers about oracle vulnerabilities. LLM-2 generates structured chain-of-thought prompts. LLM-3 identifies manipulation patterns in smart contracts. Best configuration (Haiku-Haiku-4o-mini) achieves 2.58x improvement in recall (0.667 vs 0.259) over GPTScan. Validated on 60 known vulnerabilities from 46 real-world DeFi attacks. Key insight: multi-LLM pipelines with domain knowledge extraction outperform single-model approaches for specialized vulnerability classes.

### 3b. Price Manipulation Schemes of New Crypto-Tokens in Decentralized Exchanges
- **Date**: February 2025
- **URL**: https://arxiv.org/abs/2502.10512
- **Published**: EPJ Data Science (Springer)
- **Summary**: Empirical analysis of financial impact of newly created tokens, assessing market dynamics, profitability, and liquidity manipulations. Reveals significant portion of market liquidity is trapped in honeypots. Uncovers rug pulls, sandwich attacks with higher profitability in low-liquidity pools. Key insight: new token launches on DEXs are systematically exploited through multiple manipulation vectors.

### 3c. A Two-Stage Game Model of Probabilistic Price Manipulation in DEXs
- **Date**: 2025
- **URL**: https://www.sciencedirect.com/science/article/abs/pii/S0264999325000501
- **Published**: Economic Modelling
- **Summary**: Game-theoretic model of price manipulation where manipulators reorder transactions for profit from artificial price changes. Incorporates unpredictable state transitions and strategic fee competition. Key insight: manipulation profitability depends on liquidity depth and fee structure, not just mempool visibility.

### 3d. LLM-Powered Detection of Price Manipulation in DeFi
- **Date**: 2025
- **URL**: https://arxiv.org/pdf/2510.21272
- **Summary**: LLM-based approach for detecting price manipulation patterns in DeFi protocols. Complements AiRacleX with alternative detection methodology.

---

## 4. Flash Loan Attack Detection and Prevention

### 4a. Protecting DeFi Platforms against Non-Price Flash Loan Attacks
- **Date**: March 2025
- **URL**: https://arxiv.org/abs/2503.01944
- **Published**: ACM CODASPY 2025
- **Summary**: Addresses non-price flash loan attacks (as opposed to the more studied price-manipulation variety). Proposes FlashGuard with real-time detection latency of 150.31ms, >99.93% accuracy, and 410.92ms disruption time. Uses mempool monitoring to detect attacks before confirmation and dispatches dusting counterattack transactions to change victim contract state, forcing attack reversal. Could have rescued $405.71M in historical losses. Key insight: atomicity-breaking counterattacks in the mempool are viable defenses against flash loan attacks.

### 4b. Strengthening DeFi Security: A Static Analysis Approach to Flash Loan Vulnerabilities (FlashDeFier)
- **Date**: November 2024 (updated 2025)
- **URL**: https://arxiv.org/abs/2411.01230
- **Summary**: Static taint analysis framework targeting price manipulation vulnerabilities from flash loans. Constructs inter-contract call graphs to capture data flow patterns. Identifies 76.4% of price manipulation vulnerabilities, a 30% improvement over DeFiTainter. Key insight: inter-contract call graph construction is critical for detecting flash loan attack paths that span multiple contracts.

### 4c. Prevention of Flash Loan Attacking on the Decentralized Finance System of a Public Blockchain
- **Date**: 2025
- **URL**: https://link.springer.com/chapter/10.1007/978-981-95-2566-9_29
- **Published**: Springer
- **Summary**: Multi-layered security framework integrating real-time anomaly detection, smart contract verification, decentralized governance improvements, and cross-platform intelligence sharing. Uses game-theoretic model to formalize the flash loan attack problem.

---

## 5. MEV and Sandwich Attack Analysis

### 5a. The Walls Have Ears: Unveiling Cross-Chain Sandwich Attacks in DeFi
- **Date**: November 2025
- **URL**: https://arxiv.org/abs/2511.15245
- **Summary**: Discovers that cross-chain bridges leak transaction details via source-chain events, enabling sandwich attacks on destination chains *before* transactions appear in destination mempools. Empirical study of Symbiosis protocol (Aug-Oct 2025) found cross-chain sandwich attackers achieve 21.4% profit rate vs. 0.8% for traditional MEV bots. Key insight: cross-chain bridges create a fundamentally new information asymmetry that existing MEV defenses cannot address.

### 5b. Linking MEV Attacks to Further Maximise Attackers' Gains
- **Date**: 2025
- **URL**: https://www.sciencedirect.com/science/article/pii/S2096720925000673
- **Summary**: Demonstrates that MEV attackers chain different attack types (sandwich + arbitrage) to maximize profits. Current defenses that address individual attack types are insufficient against composite strategies. Key insight: MEV attack sophistication is increasing through attack composition, not just individual technique improvement.

### 5c. Bunny Hops and Blockchain Stops: Cross-Chain MEV Detection With N-Hops
- **Date**: November 2025
- **URL**: https://arxiv.org/abs/2511.17527
- **Published**: IEEE
- **Summary**: First systematic analysis of sequence-dependent, multihop cross-chain arbitrages. Analyzed 2.4B+ swaps and 34.8M bridge transactions across 12 blockchain networks. Key insight: cross-chain MEV is still nascent (only 10 multihop instances found) but growing.

### 5d. Autonomous Agents on Blockchains: Standards, Execution Models, and Trust Boundaries
- **Date**: January 2026
- **URL**: https://arxiv.org/pdf/2601.04583
- **Summary**: Surveys how autonomous agents interact with blockchains and the security implications. MEV formalized as systematic profit extraction from front-running, back-running, and sandwich attacks. Recommends agents treat public mempools as adversarial venues. Key insight: safer agent architectures require ex-ante controls (simulation, slippage bounds, private orderflow) combined with ex-post controls (verification, recovery).

### 5e. Game-Theoretic Analysis of MEV Attacks and Mitigation Strategies
- **Date**: 2025
- **URL**: https://www.mdpi.com/2813-2203/4/3/23
- **Published**: MDPI
- **Summary**: Game-theoretic framework for analyzing MEV attacks and evaluating mitigation strategies in decentralized finance.

---

## 6. Cross-Contract Interaction Vulnerability Detection

### 6a. Enhancing Smart Contract Security Analysis with Execution Property Graphs (Clue)
- **Authors**: Tsinghua University team
- **Date**: June 2025 (ISSTA 2025)
- **URL**: https://arxiv.org/abs/2305.14046
- **Published**: ACM ISSTA 2025
- **Summary**: Introduces Execution Property Graphs (EPG) -- a unified representation interweaving call hierarchy, asset transfers, control-flow structure, and data dependencies per transaction. Supports both real-time (online) detection and postmortem (offline) analysis. EPG merges three graphs: CTG (call trace), DCFG (dynamic control-flow), and DDG (dynamic dependence). Key insight: a unified cross-contract representation that captures both control and data flow is essential for detecting attacks that span multiple contract interactions.

### 6b. Graph Attention Network-Based Multi-Agent RL Framework
- **Date**: August 2025
- **URL**: https://www.nature.com/articles/s41598-025-14032-w
- **Published**: Scientific Reports
- **Summary**: Novel approach using multi-agent Reinforcement Learning (MARL) with Hierarchical Graph Attention Network (HGAT) in a Multi-Agent Actor-Critic framework. Decomposes vulnerability detection into complementary policies for high-level and low-level reasoning. Key insight: hierarchical architectures are needed to detect vulnerabilities that emerge across multiple transactions or contract invocations.

### 6c. SEASONED: Semantic-Enhanced Self-Counterfactual Explainable Detection of Adversarial Exploiter Contracts
- **Date**: September 2025
- **URL**: https://arxiv.org/abs/2509.05681
- **Summary**: Explainable detection of adversarial exploiter contracts using semantic enhancement and counterfactual reasoning. Provides interpretable explanations for why a contract is classified as adversarial.

### 6d. Smart Contract Vulnerability Detection Using Large Language Models and Graph Structural Analysis
- **Date**: 2025
- **URL**: https://www.sciencedirect.com/org/science/article/pii/S1546221825002504
- **Published**: ScienceDirect
- **Summary**: Combines LLMs with graph structural analysis for vulnerability detection, leveraging both semantic understanding and structural properties of smart contract code.

---

## 7. Diamond Proxy Pattern Security Analysis

### 7a. The Dark Side of Upgrades: Uncovering Security Risks in Smart Contract Upgrades
- **Date**: August 2025
- **URL**: https://arxiv.org/abs/2508.02145
- **Summary**: Built dataset of 83,085 upgraded contracts and 20,902 upgrade chains. Developed taxonomy from 37 real-world security incidents, categorizing 8 types of upgrade risks. Found 31,000+ issues in active contracts. Storage collisions account for only 16.2% (6/37) of incidents, while malicious code injection (14 incidents, $115M losses) and interface collisions ($110M at risk) are more prevalent but understudied. Key insight: storage collisions get the most attention but are not the dominant upgrade vulnerability; malicious code injection and interface collisions are higher impact.

### 7b. Proxion: Uncovering Hidden Proxy Smart Contracts for Finding Collision Vulnerabilities
- **Date**: September 2024 (updated 2025)
- **URL**: https://arxiv.org/abs/2409.13563
- **Summary**: Uses EVM emulation and bytecode disassembly to reveal all proxy contracts and their logic contracts. Found 54.2% of Ethereum contracts are proxies, many with unverified "hidden contracts" as logic. Identified 1,480 additional contracts with exploitable storage collisions missed by previous tools. Key insight: the scale of proxy usage on Ethereum is far larger than previously documented, and many proxies use unverified logic contracts.

### 7c. ProxyLens: Symbolic Execution and Taint-Based Analysis of Proxy Contract Vulnerabilities
- **Date**: 2026
- **URL**: https://www.sciencedirect.com/science/article/pii/S2096720926000023
- **Summary**: Bytecode-level vulnerability detection framework for Ethereum proxy contracts that works without source code. Integrates storage structure modeling, proxy pattern recognition, and vulnerability detection. Slot recovery via symbolic execution and taint analysis achieves F1=79.50% for storage collision detection. Key insight: bytecode-only analysis can detect proxy vulnerabilities without source code access, enabling detection on unverified contracts.

### 7d. CRUSH: Not Your Type! Detecting Storage Collision Vulnerabilities
- **Date**: 2024 (NDSS)
- **URL**: https://www.ndss-symposium.org/wp-content/uploads/2024-713-paper.pdf
- **Published**: NDSS 2024
- **Summary**: Uses symbolic execution to detect Type Collisions in proxy contracts. Identified $6M+ in vulnerabilities where V2 implementation interpreted Slot 0 (address) as uint256, causing logic failure. Key insight: type collisions (same slot, different type interpretation) are as dangerous as slot collisions and harder to detect.

### 7e. First-Aid and Automated Patching for Storage Collision Vulnerabilities
- **Date**: 2025
- **URL**: https://www.usenix.org/system/files/usenixsecurity25-pan-yu.pdf
- **Published**: USENIX Security 2025
- **Summary**: Automated patching technique that replays all past transactions on patched versions to detect storage collisions that occurred historically, and reports issues before deployment.

---

## 8. Transient Storage (EIP-1153) Security Implications

### 8a. TSTORE Low-Gas Reentrancy
- **Authors**: ChainSecurity
- **Date**: 2024 (pre-Cancun analysis)
- **URL**: https://www.chainsecurity.com/blog/tstore-low-gas-reentrancy
- **Repository**: https://github.com/ChainSecurity/TSTORE-Low-Gas-Reentrancy
- **Summary**: TSTORE has no minimum gas requirement, unlike SSTORE. This means reentrancy is possible with only 2300 gas (the amount forwarded by Solidity's `transfer` and Vyper's `send`), breaking the long-held assumption that low-gas transfers are reentrancy-safe. Key insight: any contract using transient storage for reentrancy guards while relying on the 2300-gas assumption is vulnerable.

### 8b. EIP-1153 Transient Storage: Save Gas, Lose Bag (SIR.trading Analysis)
- **Authors**: TK (Verichains)
- **Date**: March 2025
- **URL**: https://blog.verichains.io/p/eip-1153-transient-storage-save-gas
- **Summary**: Detailed analysis of the SIR.trading hack ($355K, March 30, 2025) -- the first real-world exploit of EIP-1153 transient storage misuse. Protocol stored Uniswap pool address in transient slot 1, then overwrote it with mint amount. Attacker used CREATE2 to deploy contract at address matching the crafted mint amount, bypassing callback verification. Key insight: transient storage slots shared between unrelated purposes create identity spoofing vulnerabilities when values are not cleared between uses.

### 8c. Mastering Transient Storage in Uniswap V4
- **Authors**: Hacken
- **Date**: 2025
- **URL**: https://hacken.io/discover/uniswap-v4-transient-storage-security/
- **Summary**: Analysis of Uniswap V4's transient storage usage patterns and security considerations. Documents how reentrancy guards dominate current use cases (50%+ of implementations). Warns that developers avoiding slot clearing to save gas may prevent further interactions in the same transaction.

### 8d. Transient Storage in the Wild: An Impact Study on EIP-1153
- **Authors**: Dedaub
- **Date**: 2024-2025
- **URL**: https://dedaub.com/blog/transient-storage-in-the-wild-an-impact-study-on-eip-1153/
- **Summary**: Empirical study of transient storage adoption. All usage is directly from TSTORE/TLOAD opcodes via inline assembly (no Solidity native support yet), meaning usage is not widespread and could be at higher risk of vulnerability due to manual implementation.

### 8e. Transient Storage and Account Abstraction Concerns
- **Date**: 2025
- **URL**: https://hackmd.io/@-_WYFKbvSmip5m7MNB4b8A/SJFH66Eca
- **Summary**: If contracts use transient storage assuming single-user transaction frames, Account Abstraction wallets that batch multiple operations become problematic. Changing EIP behavior post-release would break existing contracts. Key insight: transient storage's transaction-scoped lifetime creates assumptions that may not hold under AA or bundled transactions.

---

## 9. LLM-Based Smart Contract Auditing

### 9a. Prompt to Pwn: Automated Exploit Generation for Smart Contracts (ReX)
- **Date**: August 2025
- **URL**: https://arxiv.org/abs/2508.01371
- **Summary**: ReX framework links LLM-based exploit synthesis to Foundry stack for end-to-end generation, compilation, execution, and verification. Evaluates 5 LLMs across 8 vulnerability classes with 38+ real incident PoCs. Strong performance on single-contract PoCs, weak on cross-contract attacks. Key insight: current LLMs are effective at single-contract exploit generation but struggle with multi-contract compositions.

### 9b. A1: AI Agent Smart Contract Exploit Generation
- **Date**: July 2025
- **URL**: https://arxiv.org/abs/2507.05558
- **Summary**: Agentic system transforming any LLM into end-to-end exploit generator with 6 domain-specific tools. Achieved 63% success rate on VERITE benchmark (up to 88.5% with premium LLMs). Extracted up to $8.59M in a single case, $9.33M total across studied incidents. Key insight: domain-specific tooling dramatically improves LLM exploit generation capability vs. raw prompting.

### 9c. LLM-SmartAudit: Advanced Smart Contract Vulnerability Detection
- **Date**: October 2024 (published IEEE TSE 2025)
- **URL**: https://arxiv.org/abs/2410.09381
- **Published**: IEEE Transactions on Software Engineering
- **Summary**: Multi-agent conversational approach with specialized agents for vulnerability detection. Outperforms all traditional auditing tools with higher accuracy and can detect complex logic vulnerabilities traditional tools miss.

### 9d. LLMBugScanner: Large Language Model based Smart Contract Auditing
- **Date**: December 2025
- **URL**: https://arxiv.org/abs/2512.02069
- **Summary**: LLM-powered approach with fine-tuning and ensemble learning for smart contract vulnerability detection. Delivers consistent accuracy gains and better generalization. Key insight: fine-tuning on domain-specific vulnerability datasets plus ensemble methods produces more reliable results than zero-shot approaches.

### 9e. LLM-BSCVM: Blockchain Smart Contract Vulnerability Management Framework
- **Date**: May 2025
- **URL**: https://arxiv.org/abs/2505.17416
- **Summary**: First complete vulnerability management framework integrating detection, cause analysis, risk assessment, repair, verification, and report generation. Key insight: end-to-end vulnerability management (not just detection) is needed for practical smart contract security.

### 9f. SmartLLM: Smart Contract Auditing using Custom Generative AI
- **Date**: February 2025
- **URL**: https://arxiv.org/abs/2502.13167
- **Summary**: Integrates Retrieval-Augmented Generation (RAG) retrieving ERC documentation during classification. Achieves 100% recall, 62.5% precision, F1=76.9%. Key insight: RAG with domain-specific documentation improves vulnerability detection recall at the cost of precision.

---

## 10. Symbolic Execution and Formal Verification

### 10a. FlawCheck: Detecting Smart Contract Vulnerabilities Based on Symbolic Execution
- **Date**: 2025
- **URL**: https://onlinelibrary.wiley.com/doi/10.1002/spy2.477
- **Published**: Security and Privacy (Wiley)
- **Summary**: Compiles source to bytecode, disassembles to opcodes, builds control flow dependencies, performs preliminary analysis during EVM simulation, then uses symbolic execution for fine-grained path-level vulnerability analysis.

### 10b. GNNSE: Smart Contract Vulnerability Detection using Symbolic Execution and GNNs
- **Date**: 2025
- **URL**: https://www.techscience.com/cmc/v86n2/64772/html
- **Published**: CMC
- **Summary**: Two-stage approach: GNNs process semantic graphs (control flow + data flow) to identify high-risk contracts, then symbolic execution performs fine-grained path analysis on flagged contracts. Key insight: GNN pre-filtering reduces the computational cost of symbolic execution by focusing it on likely-vulnerable contracts.

### 10c. Smart Contract Vulnerability Detection with Feature-Enhancement and Self-supervised Training
- **Date**: 2025
- **URL**: https://link.springer.com/chapter/10.1007/978-981-96-9849-3_17
- **Published**: Springer
- **Summary**: Feature-enhancement and self-supervised training for vulnerability detection, addressing the challenge of limited labeled vulnerability datasets.

---

## 11. Invariant-Based Detection and Runtime Monitoring

### 11a. Demystifying Invariant Effectiveness for Securing Smart Contracts
- **Date**: 2024 (updated 2025)
- **URL**: https://arxiv.org/html/2404.14580
- **Published**: ACM
- **Summary**: Empirical study of invariant effectiveness for runtime monitoring. While many runtime guarding mechanisms validate invariants to stop anomalous transactions, the actual effectiveness remains unexplored. Focuses on invariants that distinguish benign from malicious transactions across common DeFi protocols. Key insight: not all invariants are equally useful; some have high false positive rates while others miss sophisticated attacks.

### 11b. SMARTINV: Multimodal Learning for Smart Contract Invariant Inference
- **Date**: 2024 (IEEE S&P)
- **URL**: https://www.cs.columbia.edu/~junfeng/papers/smartinv-sp24.pdf
- **Published**: IEEE S&P 2024
- **Summary**: First finetuning approach that can both infer invariants and detect bugs by reasoning across multiple smart contract modalities. Key insight: multimodal learning (combining code, ABI, and transaction data) enables automatic invariant generation.

### 11c. CrossGuard: Secure Smart Contracts with Control Flow Integrity
- **Date**: 2025
- **URL**: https://www.researchgate.net/publication/390602021
- **Summary**: Enforces control flow integrity in real-time without requiring prior hack knowledge. Dynamically enforces control flow whitelisting policies at runtime. Blocked 28 of 30 analyzed attacks with 0.28% FPR and minimal gas costs. Key insight: CFI enforcement is a viable general-purpose defense that doesn't require vulnerability-specific detection rules.

---

## 12. Fuzzing and Testing

### 12a. Human Side of Smart Contract Fuzzing: An Empirical Study
- **Date**: June 2025
- **URL**: https://arxiv.org/abs/2506.07389
- **Summary**: Empirical study of how auditors actually use fuzzing tools (Echidna, Foundry). Analyzed open/closed issues from tool repositories. Key insight: precision loss bugs are severely undertested -- only coverage-guided fuzzers reliably find accumulation errors.

### 12b. Are We There Yet? Unraveling the State-of-the-Art Smart Contract Fuzzers
- **Date**: February 2024 (updated 2025)
- **URL**: https://arxiv.org/abs/2402.02973
- **Summary**: Comprehensive benchmark comparing smart contract fuzzers. Medusa has surpassed Echidna for most use cases due to parallel execution and coverage guidance. Evaluates against DeFi-specific vulnerability patterns including First Depositor Inflation (ERC-4626) and Reentrancy via Callback (ERC-721/ERC-1155).

---

## Key Takeaways for Limit Break AMM Audit

1. **Cross-contract analysis is essential**: Papers 1a, 4b, 6a show that single-contract analysis misses composability exploits. The diamond proxy + pluggable pool types + external transfer handlers create exactly this multi-contract surface.

2. **Transient storage is a live attack vector**: Papers 8a-8e plus the SIR.trading incident ($355K) confirm that EIP-1153 misuse is actively exploited. The LB-AMM's transient storage usage (slot 0xFFFF..., HOOK-001) matches the vulnerable patterns documented.

3. **LLM-based detection has specific blindspots**: Papers 9a-9f show LLMs excel at single-contract vulnerabilities but struggle with cross-contract compositions (exactly where LB-AMM's risks are highest). Multi-agent and tool-augmented approaches partially address this.

4. **Storage collisions are not the top proxy risk**: Paper 7a shows malicious code injection (14/37 incidents, $115M) and interface collisions outweigh storage collisions (6/37) in real-world proxy incidents. Diamond pattern auditing should look beyond storage layout.

5. **Rounding/precision requires compositional testing**: Paper 12a confirms precision loss bugs are undertested. The Balancer $128M hack (documented in existing reference) reinforces that individual operation correctness doesn't imply compositional correctness.

6. **Oracle manipulation detection has matured**: Paper 3a (AiRacleX) shows automated LLM-driven oracle manipulation detection is viable. The LB-AMM's price computation paths should be analyzed with similar techniques.

7. **Flash loan defenses are evolving**: Papers 4a-4c show both static (FlashDeFier) and runtime (FlashGuard) approaches. The LB-AMM should be tested for flash-loan-amplified attack paths through its diamond proxy.

8. **Cross-chain MEV is emerging**: Paper 5a shows cross-chain sandwich attacks achieve 21.4% profit rate. If LB-AMM deploys cross-chain, bridge event leakage becomes a concern.
