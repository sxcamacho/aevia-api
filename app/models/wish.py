from pydantic import BaseModel, EmailStr

class Wish(BaseModel):
    firstName: str
    lastName: str
    email: EmailStr
    country: str
    trustedContactName: str
    trustedContactEmail: EmailStr
    emailTo: EmailStr
    emailMessage: str
    cryptoWalletFrom: str
    cryptoWalletTo: str
    cryptoTokenAddress: str
    cryptoTokenType: int
    cryptoTokenId: str
    cryptoAmount: str 
    cryptoChainId: int