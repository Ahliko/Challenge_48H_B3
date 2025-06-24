from machine import Pin
import uasyncio as asyncio


from buzzer import Buzzer


class Pave:
    """
    Pave numérique
    """

    def __init__(self, row: tuple = (21, 19, 5, 18), col: tuple = (26, 27, 33, 14), buzzer: Buzzer = None):  # (18, 5, 19, 21) (27, 33, 14, 26)
        self.__buzzer = buzzer
        self.__row_pins = [Pin(i, Pin.OUT) for i in row]
        self.__col_pins = [Pin(i, Pin.IN, Pin.PULL_UP) for i in col]
        self.__key_map = [
            ['1', '2', '3', 'F'],
            ['4', '5', '6', 'E'],
            ['7', '8', '9', 'D'],
            ['A', '0', 'B', 'C']
        ]
        self.__debounce_time = 20

    async def __read_keypad(self) -> str | list[str] | None:
        """
        Read the keypad and return the key value
        :return: str | list[str] | None
        """
        for i, row_pin in enumerate(self.__row_pins):
            row_pin.value(0)
            for j, col_pin in enumerate(self.__col_pins):
                if col_pin.value() == 0:
                    await asyncio.sleep_ms(self.__debounce_time)
                    if col_pin.value() == 0:
                        row_pin.value(1)
                        if self.__buzzer is not None:
                            await self.__buzzer.beep(0.1)
                        return self.__key_map[i][j]
            row_pin.value(1)
        return None

    async def getkey(self) -> str | list[str]:
        """
        Get the key pressed
        :return: str | list[str]
        """
        while True:
            key = await self.__read_keypad()
            return key if key is not None else await asyncio.sleep_ms(150)
