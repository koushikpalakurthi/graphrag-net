# GraphRAG-Net Reasoning Output

**Query**: APT29 credential access and phishing techniques
**Model**: mock-self-test
**Calibrated Confidence Score**: 0.94 (High)
**Calibration Status**: trained_model

[SELF-TEST / MOCK MODE]

### 1. Attack Chain Reconstruction
- **Phase 1: Initial Access & Entry Vectors** — Core techniques identified: Credential Access [TA0006], Initial Access [TA0001], Persistence [TA0003].
- **Phase 2: Execution & Persistence** — Subgraph relation paths reveal connectivity between credential access and system imaging.
- **Phase 3: Lateral Movement & Impact** — Primary entities indicate multi-vector threat progression across enterprise hosts.

### 2. Actionable & Grounded Mitigations
- **[Credential Access Protection] [M1043]** -> Enforce security policy controls as indicated by STIX metadata.
- **[Boot Integrity] [M1046]** -> Enforce security policy controls as indicated by STIX metadata.
- **[Multi-factor Authentication] [M1032]** -> Enforce security policy controls as indicated by STIX metadata.

### 3. Graph Provenance & Confidence Assessment
- **Channel Consensus**: 4 primary entities confirmed by BOTH Text Factual retrieval and GNN Structural similarity.
- **Graph Triplet Density**: 25 verified 1-hop and multi-hop relation paths.
- **Confidence Rating**: HIGH (Grounding established via hybrid RRF + graph triplets).
