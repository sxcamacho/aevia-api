<p align="center">
  <img src="aevia.png" alt="Aevia Image"/>
</p>

# Aevia API  

Aevia API is a FastAPI service that enables **crypto asset inheritance** through **smart contracts and staking** using **StakeKit**.

## 📌 Key Features  

- **Create inheritance legacies** for crypto assets.  
- **Sign legacies** using Web3 signatures.  
- **Manage inheritance** across multiple blockchain networks.  
- **Stake and manage funds** via **StakeKit**, including staking, claiming rewards, and withdrawing funds.  
- **Handle trusted contacts** and notifications.  

---

## 🚀 Installation  

### 1️⃣ Clone the repository  

```bash
git clone https://github.com/BeingFounders/aevia-api
cd aevia-api
```

### 2️⃣ Create a virtual environment and install dependencies  

```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
pip install -r requirements.txt
```

### 3️⃣ Set up environment variables  

```bash
cp .env-example .env
```

Modify the `.env` file with the necessary credentials.

---

## 🔧 Environment Variables  

```env
# Supabase Configuration
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# StakeKit Configuration
STAKEKIT_API_KEY=your_stakekit_api_key
STAKEKIT_BASE_URL=https://api.stakek.it/v1

# Agent API Configuration
AGENT_API_URL=xxxxxxxxxx

# Web3 URLs for different networks
WEB3_URL_1=xxxxxxxxxx
WEB3_URL_11155111=xxxxxxxxxx
WEB3_URL_919=xxxxxxxxxx
WEB3_URL_84532=xxxxxxxxxx
WEB3_URL_5003=xxxxxxxxxx
WEB3_URL_43113=xxxxxxxxxx
WEB3_URL_57054=xxxxxxxxxx

# mnemonic phrase for investment wallets
WALLET_MNEMONIC_PHRASE=xxxxxxxxxx

# private key for the aevia smart contract operator
OPERATOR_PRIVATE_KEY=xxxxxxxxxx

```

---

## ▶️ Running the API  

1️⃣ Start the FastAPI server  

```bash
uvicorn app.main:app --reload
```

- The API will be available at: [http://localhost:8000](http://localhost:8000)  
- The **Swagger documentation** can be accessed at: [http://localhost:8000/docs](http://localhost:8000/docs)  

---

## 📌 API Endpoints  

### 🔹 **Legacies**  

| **Method** | **Endpoint** | **Description** |
|------------|-------------|----------------|
| **POST** | `/legacies` | Creates a new legacy. |
| **GET** | `/legacies/last/{user}` | Retrieves the last legacy of a user. |
| **POST** | `/legacies/{id}/sign` | Retrieves the signature payload for a legacy. |
| **PATCH** | `/legacies/{id}/sign` | Signs a legacy with a Web3 signature. |
| **POST** | `/legacies/{id}/execute` | Executes a legacy. |
| **POST** | `/legacies/{id}/stake` | Stakes the legacy funds via StakeKit. |
| **POST** | `/legacies/{id}/withdraw` | Withdraws all available funds. |
| **GET** | `/legacies/{id}/balance` | Retrieves the balance of a legacy in StakeKit. |

---

## 💎 **StakeKit Integration**  

### 🔹 **Stake (POST /legacies/{id}/stake)**  

This endpoint sends the legacy funds to **StakeKit** for staking.

#### **Process Flow:**  
1. Retrieve the investment wallet.  
2. Identify the **StakeKit integration** based on the **chain** and **token**.  
3. Execute the `enter` action in **StakeKit**.  
4. **Build and sign** the on-chain transaction.  
5. Submit the transaction and **monitor until confirmation**.  

#### **Example Response:**  

```json
{
  "status": "staked successfully",
  "transaction_url": "https://polygonscan.com/tx/0x123..."
}
```

---

### 🔹 **Withdraw (POST /legacies/{id}/withdraw)**  

This endpoint **executes all pending actions** related to a wallet's **stake balance** in **StakeKit**.

#### **Process Flow:**  
1. Retrieve the **legacy balance**.  
2. Identify **all pending actions** such as unstaked funds, claim rewards, and withdrawals.  
3. Execute each **pending action** accordingly.  
4. **Build and sign transactions**.  
5. Submit transactions and **monitor until confirmation**.  

#### **Example Response:**  

```json
[
  {
    "groupId": "83edaa5c-1037-5bb6-b883-d3534d6a1faa",
    "status": "WITHDRAW successfully executed",
    "transaction_url": "https://etherscan.io/tx/0x123..."
  }
]

```

---

## ⚙️ **StakeKit Transaction Flow**  

Each **StakeKit operation** follows a structured **transaction execution flow**, ensuring consistency across all actions:  

1️⃣ **Post Action** → Sends the request to **StakeKit** to initiate the action.  
2️⃣ **Get Current Gas** → Retrieves current gas prices to optimize transactions.  
3️⃣ **Construct Transaction** → Builds the raw unsigned transaction.  
4️⃣ **Sign Transaction** → Signs the transaction with the investment wallet's **private key**.  
5️⃣ **Submit Transaction** → Submits the signed transaction to the **blockchain**.  
6️⃣ **Get Transaction Status** → Monitors the transaction **until confirmation**.  

🔹 This transaction flow is used for the following actions:  

| **Action** | **Description** |
|------------|----------------|
| **Stake (Enter)** | Deposits funds into a staking position. |
| **Unstake (Exit)** | Starts the unstaking process. |
| **Withdraw** | Moves claimed funds back to the user's wallet. |

---

## 📊 **Database Schema**  

Aevia API uses **Supabase** as its database backend, with the following primary tables:

### 🔹 **Legacies Table (legacies)**  

| **Field** | **Description** |
|-----------|---------------|
| `id` | Unique identifier of the legacy. |
| `blockchain_id` | Random blockchain identifier for internal tracking. |
| `chain_id` | Blockchain network identifier. |
| `token_type` | Type of token (ERC20, ERC721, etc.). |
| `token_address` | Address of the asset. |
| `token_id` | Token ID (for NFTs). |
| `amount` | Amount of assets allocated to the legacy. |
| `wallet` | Owner's wallet address. |
| `heir_wallet` | Beneficiary's wallet address. |
| `signature` | Web3 signature of the owner. |
| `name` | Name of the legacy. |
| `telegram_id` | Telegram ID of the owner. |
| `telegram_id_emergency` | Emergency contact's Telegram ID. |
| `telegram_id_heir` | Heir's Telegram ID. |
| `contract_address` | Smart contract address linked to the legacy. |
| `signal_confirmation_retries` | Number of retries for confirmation signals. |
| `signal_requested_at` | Timestamp when the signal was requested. |
| `signal_received_at` | Timestamp when the signal was received. |
| `investment_enabled` | Indicates if staking is enabled. |
| `investment_risk` | Risk level of the investment. |

---

### 🔹 **Investment Wallets Table (investment_wallets)**  

| **Field** | **Description** |
|-----------|---------------|
| `id` | Unique identifier of the investment wallet. |
| `index` | Index of the mnemonic that corresponds to this investment wallet. |
| `legacy_id` | Foreign key linking the wallet to a legacy. |
| `wallet_address` | Address of the investment wallet. |
| `staked_at` | Timestamp when the funds were staked. |
| `unstaked_at` | Timestamp when the funds were unstaked. |

---

### 🔹 **Contracts Table (contracts)**  

| **Field** | **Description** |
|-----------|---------------|
| `id` | Unique identifier of the contract. |
| `name` | Name of the contract. |
| `chain_id` | Blockchain network identifier. |
| `address` | Smart contract address. |
| `abi` | Contract ABI (Application Binary Interface). |

---

Each table plays a critical role in handling crypto inheritance, staking, and fund withdrawals within the **Aevia API** ecosystem. 🚀  