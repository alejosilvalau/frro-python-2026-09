from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.properties import ListProperty

class CalcButton(Button):
    bg_color = ListProperty([0.18, 0.18, 0.22, 1]) 


class CalculatorLayout(BoxLayout):
    def button_press(self, text):
        display = self.ids.display
        current = display.text

        if text == 'C':
            display.text = '0'
        elif text == '⌫':
            display.text = current[:-1] if len(current) > 1 else '0'
        elif text == '=':
            try:
                expression = current.replace('×', '*').replace('÷', '/')
                result = eval(expression)
                display.text = str(int(result) if result == int(result) else round(result, 8))
            except Exception:
                display.text = 'Error'
        elif text == '+/-':
            try:
                val = float(current)
                display.text = str(int(-val) if -val == int(-val) else -val)
            except Exception:
                pass
        elif text == '%':
            try:
                val = float(current)
                result = val / 100
                display.text = str(int(result) if result == int(result) else result)
            except Exception:
                pass
        else:
            if current == '0' and text not in '.+-×÷':
                display.text = text
            elif current == 'Error':
                display.text = text
            else:
                display.text = current + text


class CalculatorApp(App):
    def build(self):
        return CalculatorLayout()


if __name__ == '__main__':
    CalculatorApp().run()
