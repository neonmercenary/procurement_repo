# ❄️ Zero Degree & SnowGate: The Institutional Settlement Layer

**Zero Degree** is a high-performance procurement engine bridging legacy Enterprise Resource Planning (ERP) systems with decentralized, AUTONOMOUS settlement on Avalanche.

By leveraging **SnowGate**, a programmable treasury firewall built on **Avalanche**, we eliminate the "T+32" day settlement gap, replacing manual reconciliation with **Atomic Delivery-vs-Payment (DvP)**.

---

## 🏗️ Architectural Overview

The system operates as a **Dual-Layer Procurement Stack**:

1. **The Commerce Layer (Zero Degree):** A FastAPI-based engine that intercepts Purchase Requisitions (PR) from legacy systems like SAP. It handles catalog management and merchant discovery.
2. **The Security Layer (SnowGate):** A Vyper-native treasury firewall. It enforces on-chain spend policies, locking corporate budgets until cryptographic proof of delivery is provided.
3. **The Agentic Worker:** An asynchronous Python monitor that bridges the gap. It watches for `OrderCompleted` events on Avalanche and triggers "Goods Receipt" (GR) updates in the ERP.

---

## 🔒 Security & Technical Specifications

### **Vyper 0.4.0 Smart Contracts**

We chose **Vyper** for the SnowGate core because of its proximity to Python and its focus on auditability.

* **Re-entrancy Protection:** Hardcoded at the compiler level.
* **SnowGate Registry:** Implements a mirrored identity system with **ERC-8004**, ensuring that only verified corporate agents can authorize spend.
* **Stake-Back Settlement:** Merchants must maintain a minimum USDC stake to participate, creating a slashed-incentive model for fulfillment.


## 🔒 Security & Technical Specifications

### **The "Programmable Firewall" Logic**
SnowGate acts as a **State-Aware Vault**. Unlike standard wallets, it enforces **Contextual Spend Limits**:
* **Temporal Locks:** Trade validity is anchored to block timestamps.
* **Atomic Settlement:** Funds never leave the corporate vault until the Merchant provides cryptographic proof of fulfillment.
* **Session Isolation:** Budget is siloed per relayer/agent, preventing single-point-of-failure treasury drains.

### **Zero-Knowledge Handshake**
The system utilizes a proprietary pass-through logic to verify settlement between the VendorShop and SnowGate. This ensures the Corporate Vault only settles orders verified by the internal state machine.
---

# 📺 Project Walkthrough

[![Zero Degree & SnowGate Demo](https://raw.githubusercontent.com/lucas-mancini/resources/main/video-placeholder.png)](https://www.loom.com/share/b3d4f62d46bf48e2af6c27d002454c16)
> *Click the image above to watch the 5-minute technical walkthrough.*

---

## ⚡ Technical Stack

| Component | Technology | Role |
| --- | --- | --- |
| **Blockchain** | Avalanche Fuji | Sub-second finality and institutional throughput. |
| **Contracts** | Vyper 0.4.0 | Secure, auditable treasury logic. |
| **Backend** | FastAPI / Python 3.12 | ERP integration and Business Logic. |
| **Orchestration** | `uv` | Lightning-fast environment and dependency management. |
| **Identity** | ERC-8004 | Decentralized institutional identity. |
| **Framework** |   ApeWorx | Ethereum development framework for smart contract management. |
| **Indexing** | Routescan API | Source for real-time event monitoring and order detection. |

---

## 🛠️ Installation & Deployment

### **Prerequisites**

* [Python 3.12+](https://www.python.org/)
* [uv](https://github.com/astral-sh/uv)
* [ApeWorx](https://apeworx.io/)
* [Vyperlang](https://vyperlang.org/)

### **Setup**


```bash
# Clone the repository
git clone https://github.com/neonmercenary/procurement_repo

```

#### Run Zero degree    - Terminal 1
```bash
cd zero_degree/

# Synchronize virtual environment
uv sync

# Deploy Zerodegree.vy
uv run ape run deploy --network avalanche:fuji

# Take the contract address to snowgate env (Link to Snowgate)

# Make Executable
chmod +x ./start_zd.sh
./start_zd.sh

```

#### Run SnowGate  - Terminal 2
```bash
cd snowgate/

# Synchronize virtual environment
uv sync

# Deploy SnowGateSession.vy
uv run ape run deploy --network avalanche:fuji

# Make Executable
chmod +x ./start_sg.sh
./start_sg.sh
```

#### Run the Mock SAP PR    - Terminal 3
```bash
# Simulate the SAP PR request - Parent folder (~/procurement_repo)
uv sync
uv run simulate_sap.py

```


---
## 🤝 Community & Support
Telegram: https://t.me/theinternetgod

---

### Built for the 2026 Avalanche Build Games.