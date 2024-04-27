import json
from datetime import datetime 
import time
import zoneinfo
import random
import requests
from dataclasses import dataclass, field
from bs4 import BeautifulSoup

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

from typing import Annotated


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

app = FastAPI()


def fake_hash_password(password: str):
    return "fakehashed" + password


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None


class UserInDB(User):
    hashed_password: str


def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)


def fake_decode_token(token):
    # This doesn't provide any security at all
    # Check the next version
    user = get_user(fake_users_db, token)
    return user


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    user = fake_decode_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


@app.post("/token")
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    user_dict = fake_users_db.get(form_data.username)
    if not user_dict:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    user = UserInDB(**user_dict)
    hashed_password = fake_hash_password(form_data.password)
    if not hashed_password == user.hashed_password:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    return {"access_token": user.username, "token_type": "bearer"}


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
