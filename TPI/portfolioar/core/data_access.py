from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.hashers import make_password
from .models import User, Sector, Broker, Stock


def get_user_by_id(user_id):
    return User.objects.get(id=user_id)


def get_user_by_email(email):
    return User.objects.filter(email=email).first()


def create_user(first_name, last_name, email, password, phone=None, birthdate=None):
    if User.objects.filter(email=email).exists():
        raise ValueError("El email ya está registrado")

    user = User(
        first_name=first_name,
        last_name=last_name,
        email=email,
        username=email,
        phone=phone,
        birthdate=birthdate,
        password=make_password(password)
    )
    user.save()
    return user


def authenticate_user(email, password):
    user = User.objects.filter(email=email).first()
    if user is not None and user.check_password(password):
        return user
    return None


def login_user(request, user):
    login(request, user)


def logout_user(request):
    logout(request)


def get_all_sectors():
    return Sector.objects.all()


def get_sector_by_id(sector_id):
    return Sector.objects.get(id=sector_id)


def create_sector(name, description='', primary=False):
    sector = Sector(name=name, description=description, primary=primary)
    sector.save()
    return sector


def get_all_brokers():
    return Broker.objects.all()


def get_broker_by_id(broker_id):
    return Broker.objects.get(id=broker_id)


def create_broker(name, link=''):
    broker = Broker(name=name, link=link)
    broker.save()
    return broker


def get_all_stocks():
    return Stock.objects.all()


def get_stock_by_id(stock_id):
    return Stock.objects.get(id=stock_id)


def get_stock_by_ticker(ticker):
    return Stock.objects.filter(ticker=ticker).first()


def create_stock(ticker, company_name, sector=None):
    stock = Stock(ticker=ticker, company_name=company_name, sector=sector)
    stock.save()
    return stock


def get_stock_by_sector(sector_id):
    return Stock.objects.filter(sector_id=sector_id)
