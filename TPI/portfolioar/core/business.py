from .data_access import (
    get_user_by_id, get_user_by_email, create_user,
    authenticate_user, login_user, logout_user,
    get_all_sectors, get_sector_by_id, create_sector,
    get_all_brokers, get_broker_by_id, create_broker,
    get_all_stocks, get_stock_by_id, get_stock_by_ticker, create_stock,
    get_stock_by_sector
)


class AuthManager:
    def register(self, first_name, last_name, email, password, phone=None, birthdate=None):
        if get_user_by_email(email):
            raise ValueError("El email ya está registrado")

        if len(password) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")

        return create_user(first_name, last_name, email, password, phone, birthdate)

    def login(self, request, email, password):
        user = authenticate_user(email, password)
        if user is None:
            raise ValueError("Credenciales inválidas")
        login_user(request, user)
        return user

    def logout(self, request):
        logout_user(request)

    def get_user(self, user_id):
        return get_user_by_id(user_id)

    def change_password(self, user, old_password, new_password):
        if not user.check_password(old_password):
            raise ValueError("La contraseña actual es incorrecta")
        if len(new_password) < 8:
            raise ValueError("La nueva contraseña debe tener al menos 8 caracteres")
        user.set_password(new_password)
        user.save()
        return user


class SectorManager:
    def get_all(self):
        return get_all_sectors()

    def get_by_id(self, sector_id):
        return get_sector_by_id(sector_id)

    def create(self, name, description='', primary=False):
        return create_sector(name, description, primary)


class BrokerManager:
    def get_all(self):
        return get_all_brokers()

    def get_by_id(self, broker_id):
        return get_broker_by_id(broker_id)

    def create(self, name, link=''):
        return create_broker(name, link)


class StockManager:
    def get_all(self):
        return get_all_stocks()

    def get_by_id(self, stock_id):
        return get_stock_by_id(stock_id)

    def get_by_ticker(self, ticker):
        return get_stock_by_ticker(ticker)

    def create(self, ticker, company_name, sector=None):
        return create_stock(ticker, company_name, sector)

    def get_by_sector(self, sector_id):
        return get_stock_by_sector(sector_id)
