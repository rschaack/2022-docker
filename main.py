import json
import time
import zoneinfo

import random
import requests

from dataclasses import dataclass, field
from bs4 import BeautifulSoup

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel



SECRET_KEY = "da4c5f61de2feb6212cefdc710e183b7b3dbb0e05be54f122929a60c9063b201"
ALGORITHM = "HS256"
ACCESS_TOKE_EXPIRE_MINUTES = 30


fake_users_db = {
    "johndoe": {
        "username": "johndoe",
        "full_name": "John Doe",
        "email": "johndoe@example.com",
        "hashed_password": "fakehashedsecret",
        "disabled": False,
    },
    "alice": {
        "username": "alice",
        "full_name": "Alice Wonderson",
        "email": "alice@example.com",
        "hashed_password": "fakehashedsecret2",
        "disabled": True,
    },
    "roland": {
        "username": "roland",
        "full_name": "Roland Schaack",
        "email": "roland@schaack.info",
        "hashed_password": "fakehashedsecret3",
        "disabled": True,
    },
}


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None


class UserInDB(User):
    hashed_password: str

pwd_context = CryptContext(schemes=["bcrypt"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app = FastAPI()


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)
    

def authenticate_user(fake_db, username: str, password: str):
    user = get_user(fake_db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

                        


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = get_user(fake_users_db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


@app.post("/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:    
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKE_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="Bearer")


@app.get("/users/me")
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    return current_user



#-----------------------------------------------------------------------------


@dataclass
class Channel:
    id: str
    name: str
    tags: list[str] = field(default_factory=list)
    description: str = ""

@dataclass
class Price:
    ticker: str
    price: float
    time: str


channels: dict[str, Channel] = {}

with open("channels.json", encoding="utf8") as file:
    channels_raw = json.load(file)
    for channel_raw in channels_raw:
        channel = Channel(**channel_raw)
        channels[channel.id] = channel


@app.get("/")
def read_root() -> Response:
    return Response("The server is running.")


@app.get("/channels/{channel_id}", response_model=Channel)
def read_item(channel_id: str) -> Channel:
    if channel_id not in channels:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channels[channel_id]

@app.get("/prices/{ticker_id}", response_model=Price)
def read_item(ticker_id: str) -> Price:
    price_record = FinancialTimes(ticker_id)
    return Price(price_record.ticker,price_record.price,price_record.priceTime)

@app.get("/testprices/{ticker_id}", response_model=Price)
def read_item(ticker_id: str) -> Price:
    price_record = Test(ticker_id)
    return Price(price_record.ticker,price_record.price,price_record.priceTime)


class FinancialTimes:
    def __init__(self, ticker):
        self.ticker = ticker
        URL = "https://markets.ft.com/data/funds/tearsheet/summary?s=" + self.ticker
        page = requests.get(URL)
        time.sleep(random.randint(1,100)/100)
        self.priceTime = datetime.now(zoneinfo.ZoneInfo("Europe/London")).strftime("%d/%m/%Y,%H:%M")
        soup = BeautifulSoup(page.content, "html.parser")
        try:
            self.price = soup.find(class_="mod-ui-data-list__value").text.strip().replace(",","")
        except:
            self.price = "No price found"

# Used when I don't want to scrape a real website
class Test:
    def __init__(self, ticker):
        self.ticker = ticker
        self.priceTime = datetime.now(zoneinfo.ZoneInfo("Europe/London")).strftime("%d/%m/%Y,%H:%M")
        try:
            self.price = 999
        except:
            self.price = "No price found"
