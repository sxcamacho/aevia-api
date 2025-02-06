<p align="center">
  <img src="aevia.png" alt="Aevia Logo"/>
</p>

# Aevia API

A FastAPI service that manages crypto asset inheritance through smart contracts.

## Overview

This API allows users to:
- Create inheritance legacies for crypto assets
- Sign legacies using web3 signatures
- Manage crypto asset inheritance across different chains
- Handle trusted contacts and notifications

## Installation

1. Clone the repository
```bash
git clone https://github.com/BeingFounders/aevia-api
cd aevia-api
```

2. Create virtual environment and install dependencies
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
pip install -r requirements.txt
```

3. Set up environment variables by copying `.env-example` to `.env`:
```bash
cp .env-example .env
```

## Environment Variables

```env
# Supabase Configuration
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
```

## Running the API

1. Start the FastAPI server:
```bash
uvicorn app.main:app --reload
```

2. The API will be available at `http://localhost:8000`
3. Access the Swagger documentation at `http://localhost:8000/docs`

## API Documentation

### Endpoints

#### Legacies
- `POST /legacies` - Create a new legacy
- `POST /legacies/{legacy_id}/sign` - Get signature payload for a legacy
- `PATCH /legacies/{legacy_id}/sign` - Set signature for a legacy

#### Contracts
- `GET /contracts` - List all contracts
- `GET /contracts/{chain_id}/{name}` - Get contract by chain and name
- `POST /contracts` - Create a new contract

## Database Schema

The API uses Supabase with the following main tables:
- `legacies` - Stores inheritance information
- `contracts` - Stores smart contract addresses and ABIs