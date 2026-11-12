# GraphRAG-Net Reasoning Output

**Query**: APT29 credential access
**Model**: mock-self-test
**Calibrated Confidence Score**: 0.85 (High)
**Calibration Status**: trained_model

[SELF-TEST / MOCK MODE]

### 1. Attack Chain Reconstruction
- **Phase 1: Initial Access & Entry Vectors** — Core entities identified: Credential Access [TA0006].
- **Phase 2: Execution & Persistence** — Subgraph relation paths reveal connectivity across weaknesses, attack patterns, and system execution vectors.
- **Phase 3: Lateral Movement & Impact** — Primary entities indicate multi-vector threat progression across enterprise hosts.

### 2. Actionable & Grounded Mitigations
- **Target**: `[Credential Access Protection] [M1043]`
  - **Mitigation Control**: Security Policy Control
  - **Implementation Action**: Implement hardening standards as indicated by STIX metadata.

### 3. Graph Provenance & Confidence Assessment
- **Channel Consensus**: 3 primary entities confirmed by BOTH Text Factual retrieval and GNN Structural similarity.
- **Graph Triplet Density**: 25 verified 1-hop and multi-hop relation paths.
- **Confidence Rating**: HIGH (Grounding established via hybrid RRF + graph triplets).
