from pydantic import BaseModel

class Legacy(BaseModel):
    firstName: str
    lastName: str
    email: str
    country: str
    trustedContactName: str
    trustedContactEmail: str
    emailTo: str
    emailMessage: str | None = None
    cryptoWalletFrom: str
    cryptoWalletTo: str | None = None
    cryptoTokenAddress: str
    cryptoTokenType: int
    cryptoTokenId: str | None = None
    cryptoAmount: str | None = None
    cryptoChainId: int
    cryptoSignature: str | None = None