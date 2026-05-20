from kivy.app import App
from kivy.factory import Factory
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.dropdown import DropDown


class CalculatorScreen(BoxLayout):
    first_value = StringProperty("1")
    operation = StringProperty("+")
    second_value = StringProperty("1")
    result = StringProperty("2")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.first_dropdown = self.create_dropdown(
            ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"], self.update_first
        )
        self.operation_dropdown = self.create_dropdown(
            ["+", "−", "×", "÷"], self.update_operation
        )
        self.second_dropdown = self.create_dropdown(
            ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"], self.update_second
        )

    def create_dropdown(self, values, callback):
        dropdown = DropDown()
        for value in values:
            btn = Factory.DropdownItem(text=value)
            btn.bind(on_release=lambda btn: dropdown.select(btn.text))
            btn.bind(on_release=lambda btn: callback(btn.text))
            dropdown.add_widget(btn)
        dropdown.bind(
            on_select=lambda dropdown, value: setattr(dropdown, "value", value)
        )
        return dropdown

    def show_first_dropdown(self, button):
        self.first_dropdown.open(button)

    def show_operation_dropdown(self, button):
        self.operation_dropdown.open(button)

    def show_second_dropdown(self, button):
        self.second_dropdown.open(button)

    def update_first(self, text):
        self.first_value = text
        self.calculate()

    def update_operation(self, text):
        self.operation = text
        self.calculate()

    def update_second(self, text):
        self.second_value = text
        self.calculate()

    def calculate(self):
        try:
            n1 = int(self.first_value)
            n2 = int(self.second_value)
            op = self.operation

            if op == "+":
                res = n1 + n2
            elif op == "−":
                res = n1 - n2
            elif op == "×":
                res = n1 * n2
            elif op == "÷":
                res = n1 / n2 if n2 != 0 else "Error"
                if res == int(res):
                    res = int(res)
                else:
                    res = round(res, 2)

            self.result = str(res)
        except:
            self.result = "Error"


class CalculatorApp(App):
    def build(self):
        return CalculatorScreen()


if __name__ == "__main__":
    CalculatorApp().run()
