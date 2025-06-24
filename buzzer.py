import machine
import uasyncio as asyncio


class Buzzer:
    def __init__(self, pin, freq=1000):
        self.pin = machine.PWM(machine.Pin(pin, machine.Pin.OUT))
        self.freq = freq
        self.__off()

    def __off(self):
        self.pin.duty_u16(0)

    def __on(self):
        self.pin.duty_u16(self.freq)

    async def beep(self, duration):
        self.__on()
        await asyncio.sleep(duration)
        self.__off()

    def _Buzzer__off(self):
        self.pin.duty_u16(0)

    def _Buzzer__on(self):
        self.pin.duty_u16(self.freq)

    @property
    def freq(self):
        return self.pin.freq()

    @freq.setter
    def freq(self, value):
        self.pin.freq(value)