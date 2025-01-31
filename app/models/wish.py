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
    cryptoWalletTo: str
    cryptoTokenAddress: str
    cryptoAmount: str 