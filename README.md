# ❄️ Zero Degree & SnowGate: The Institutional Settlement Layer

**Zero Degree** is a high-performance procurement engine bridging legacy Enterprise Resource Planning (ERP) systems with decentralized, real-world asset (RWA) settlement.

By leveraging **SnowGate**, a programmable treasury firewall built on **Avalanche**, we eliminate the "T+32" day settlement gap, replacing manual reconciliation with **Atomic Delivery-vs-Payment (DvP)**.

---

## 🏗️ Architectural Overview

The system operates as a **Dual-Layer Procurement Stack**:

1. **The Commerce Layer (Zero Degree):** A FastAPI-based engine that intercepts Purchase Requisitions (PR) from legacy systems like SAP. It handles catalog management and merchant discovery.
2. **The Security Layer (SnowGate):** A Vyper-native treasury firewall. It enforces on-chain spend policies, locking corporate budgets until cryptographic proof of delivery is provided.
3. **The Agentic Worker:** An asynchronous Python monitor that bridges the gap. It watches for `ProductDelivered` events on Avalanche and triggers "Goods Receipt" (GR) updates in the ERP.

---

## 🔒 Security & Technical Specifications

### **Vyper 0.4.0 Smart Contracts**

We chose **Vyper** for the SnowGate core because of its proximity to Python and its focus on auditability.

* **Re-entrancy Protection:** Hardcoded at the compiler level.
* **SnowGate Registry:** Implements a mirrored identity system with **ERC-8004**, ensuring that only verified corporate agents can authorize spend.
* **Stake-Back Settlement:** Merchants must maintain a minimum USDC stake to participate, creating a slashed-incentive model for fulfillment.

### **The "Firewall" Logic**

Unlike standard Web3 wallets, SnowGate acts as a **State-Aware Vault**. It doesn't just send money; it verifies the **Temporal Validity** of a trade using block timestamps. If a vendor fails to deliver within the block-anchored window, the corporate budget is automatically unlocked and reverted.

---

## ⚡ Technical Stack

| Component | Technology | Role |
| --- | --- | --- |
| **Blockchain** | Avalanche Fuji | Sub-second finality and institutional throughput. |
| **Contracts** | Vyper 0.4.0 | Secure, auditable treasury logic. |
| **Backend** | FastAPI / Python 3.12 | ERP integration and Business Logic. |
| **Orchestration** | `uv` | Lightning-fast environment and dependency management. |
| **Identity** | ERC-8004 | Decentralized institutional identity. |

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

#### Run Zero degree
```bash
# Launch Zero degree - Terminal 1
cd zero_degree/

# Synchronize virtual environment
uv sync

# Make Executable
chmod +x ./start_zd.sh
./start_sg.sh

# Deploy Zerodegree.vy
uv run ape run deploy --network avalanche:fuji
```

#### Run SnowGate
```bash
# Launch SnowGate - Terminal 2
cd snowgate/

# Synchronize virtual environment
uv sync

# Deploy SnowGateSession.vy
uv run ape run deploy --network avalanche:fuji

# Make Executable
chmod +x ./start_sg.sh
./start_sg.sh
```

#### Run the Mock SAP PR
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