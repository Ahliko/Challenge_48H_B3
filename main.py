import uasyncio as asyncio
import test


def main():
    try:
        asyncio.run(test.main())
    except KeyboardInterrupt:
        print("\nArrêt du système")
    except Exception as e:
        print(f"Erreur fatale: {e}")

    # from pave_numerique import Pave
    #
    # pave = Pave()
    # while 1:
    #     key = asyncio.run(pave.getkey())
    #     if key:
    #         print(f"Touche pressée: {key}")
    #     else:
    #         print("Aucune touche pressée")
    #     asyncio.sleep(0.5)


if __name__ == "__main__":
    main()
