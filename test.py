from machine import ADC, Pin, unique_id
import time
import network

from buzzer import Buzzer
from umqttsimple import MQTTClient
import ubinascii
import gc
import uasyncio as asyncio
from pave_numerique import Pave

ssid = 'AZERTY'
password = 'lollollol'
mqtt_server = "broker.emqx.io"
client_id = ubinascii.hexlify(unique_id())
topic_pub = "maison/porte/etat"

adc = ADC(Pin(35))
adc.atten(ADC.ATTN_11DB)
led_verte = Pin(32, Pin.OUT)
led_rouge = Pin(25, Pin.OUT)

etat_porte = "Fermée"
dernier_etat_publie = ""
alarme_activee = False
alarme_en_alerte = False
code_alarme = "1234"
temps_ouverture = 0
delai_alerte = 10
saisie_code_en_cours = False
code_saisi = ""

buzzer = Buzzer(13)
pave = Pave(buzzer=buzzer)

def connecter_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print('Connexion au réseau WiFi...')
        wlan.connect(ssid, password)
        max_wait = 20
        while max_wait > 0:
            if wlan.isconnected():
                break
            max_wait -= 1
            print('Attente de connexion...')
            time.sleep(1)
        if wlan.isconnected():
            print('Connecté au WiFi')
            print('Adresse IP:', wlan.ifconfig()[0])
        else:
            print('Échec de connexion WiFi')
            return False
    return True

def connecter_mqtt():
    client = MQTTClient(client_id, mqtt_server, keepalive=60)
    try:
        client.connect()
        print(f'Connecté au broker MQTT: {mqtt_server}')
        return client
    except Exception as e:
        print(f'Échec de connexion au broker MQTT: {e}')
        return None

async def clignoter_led(pin, nb_fois, duree_ms=200):
    for _ in range(nb_fois):
        pin.value(1)
        await asyncio.sleep_ms(duree_ms)
        pin.value(0)
        await asyncio.sleep_ms(duree_ms)

async def son_activation():
    buzzer.freq = 800
    await buzzer.beep(0.2)
    await asyncio.sleep_ms(50)
    buzzer.freq = 1000
    await buzzer.beep(0.2)

async def son_desactivation():
    buzzer.freq = 1000
    await buzzer.beep(0.15)
    await asyncio.sleep_ms(50)
    buzzer.freq = 800
    await buzzer.beep(0.15)
    await asyncio.sleep_ms(50)
    buzzer.freq = 600
    await buzzer.beep(0.2)

async def son_alerte_imminente():
    for _ in range(5):
        buzzer.freq = 1500
        await buzzer.beep(0.1)
        await asyncio.sleep_ms(200)

async def son_alerte_continue():
    while alarme_en_alerte:
        buzzer.freq = 2000
        await buzzer.beep(0.3)
        await asyncio.sleep_ms(100)
        buzzer.freq = 1800
        await buzzer.beep(0.3)
        await asyncio.sleep_ms(100)

async def gerer_alarme():
    global alarme_activee, alarme_en_alerte, etat_porte, temps_ouverture

    while True:
        if alarme_activee and etat_porte == "Ouverte" and not alarme_en_alerte:
            if temps_ouverture == 0:
                temps_ouverture = time.time()
                print("⚠️ Porte ouverte - Délai de 10s avant alerte")
                asyncio.create_task(son_alerte_imminente())
            elif time.time() - temps_ouverture >= delai_alerte:
                alarme_en_alerte = True
                print("🚨 ALERTE ! Intrusion détectée !")
                asyncio.create_task(clignoter_alerte())
                asyncio.create_task(son_alerte_continue())

        elif etat_porte == "Fermée":
            temps_ouverture = 0
            if alarme_en_alerte:
                alarme_en_alerte = False
                print("Porte fermée - Alerte annulée")

        await asyncio.sleep_ms(100)

async def clignoter_alerte():
    while alarme_en_alerte:
        led_rouge.value(1)
        await asyncio.sleep_ms(100)
        led_rouge.value(0)
        await asyncio.sleep_ms(100)

async def gerer_pave():
    global alarme_activee, alarme_en_alerte, code_alarme, saisie_code_en_cours, code_saisi

    while True:
        try:
            touche = await pave.getkey()

            if touche is not None:
                print(f"Touche pressée: {touche}")

                if touche == 'F' and not saisie_code_en_cours:
                    if not alarme_activee:
                        alarme_activee = True
                        alarme_en_alerte = False
                        print("🔒 Alarme ACTIVÉE")
                        await clignoter_led(led_verte, 3, 150)
                        await son_activation()
                    else:
                        print("Alarme déjà activée")

                elif touche in '0123456789':
                    if alarme_activee and not saisie_code_en_cours:
                        saisie_code_en_cours = True
                        code_saisi = touche
                        print(f"Saisie du code: {'*' * len(code_saisi)}")
                        await asyncio.sleep(0.3)
                    elif saisie_code_en_cours:
                        code_saisi += touche
                        print(f"Saisie du code: {'*' * len(code_saisi)}")

                        if len(code_saisi) >= 4:
                            if code_saisi == code_alarme:
                                alarme_activee = False
                                alarme_en_alerte = False
                                saisie_code_en_cours = False
                                print("🔓 Alarme DÉSACTIVÉE")
                                await clignoter_led(led_verte, 5, 100)
                                await son_desactivation()
                            else:
                                print("❌ Code incorrect!")
                                saisie_code_en_cours = False
                                await clignoter_led(led_rouge, 3, 200)
                                buzzer.freq = 300
                                await buzzer.beep(0.5)
                            code_saisi = ""
                        await asyncio.sleep(0.3)

                elif touche == 'C' and saisie_code_en_cours:
                    saisie_code_en_cours = False
                    code_saisi = ""
                    print("Saisie annulée")

                elif touche == 'E' and saisie_code_en_cours:
                    if code_saisi == code_alarme:
                        alarme_activee = False
                        alarme_en_alerte = False
                        saisie_code_en_cours = False
                        print("🔓 Alarme DÉSACTIVÉE")
                        await clignoter_led(led_verte, 5, 100)
                        await son_desactivation()
                    else:
                        print("❌ Code incorrect!")
                        saisie_code_en_cours = False
                        await clignoter_led(led_rouge, 3, 200)
                        buzzer.freq = 300
                        await buzzer.beep(0.5)
                    code_saisi = ""

        except Exception as e:
            print(f"Erreur pavé numérique: {e}")
            await asyncio.sleep_ms(100)

async def surveiller_porte():
    global etat_porte, dernier_etat_publie, mqtt_client

    while True:
        try:
            valeur = adc.read()
            tension = valeur * 3.3 / 4095

            if valeur > 3500:
                etat_porte = "Fermée"
            else:
                etat_porte = "Ouverte"

            if not alarme_en_alerte:
                if etat_porte == "Fermée":
                    led_verte.value(1)
                    led_rouge.value(0)
                else:
                    if not alarme_activee:
                        led_verte.value(0)
                        led_rouge.value(1)
                    else:
                        led_verte.value(0)

            try:
                if mqtt_client:
                    mqtt_client.check_msg()

                    etat_complet = etat_porte
                    if alarme_activee:
                        etat_complet += " - Alarme: ON"
                        if alarme_en_alerte:
                            etat_complet += " - ALERTE!"
                    else:
                        etat_complet += " - Alarme: OFF"

                    if saisie_code_en_cours:
                        etat_complet += " - Saisie code..."

                    mqtt_client.publish(topic_pub, etat_complet)

                    if dernier_etat_publie != etat_complet:
                        print(f"État publié: {etat_complet}")
                        dernier_etat_publie = etat_complet

            except Exception as e:
                print(f"Erreur MQTT: {e}")
                mqtt_client = connecter_mqtt()

            gc.collect()
            await asyncio.sleep_ms(500)

        except Exception as e:
            print(f"Erreur surveillance porte: {e}")
            await asyncio.sleep_ms(1000)

async def main():
    global mqtt_client

    print("=== Système de surveillance avec alarme ===")
    print("Commandes pavé numérique:")
    print("- F: Activer l'alarme")
    print("- 0-9: Saisir le code pour désactiver")
    print("- E: Valider le code")
    print("- C: Annuler la saisie")
    print(f"- Code par défaut: {code_alarme}")
    print()

    if not connecter_wifi():
        print("Impossible de continuer sans WiFi")
        return

    mqtt_client = connecter_mqtt()
    if mqtt_client:
        mqtt_client.publish(topic_pub, "Système démarré - Alarme OFF")

    try:
        await asyncio.gather(
            surveiller_porte(),
            gerer_pave(),
            gerer_alarme()
        )
    except Exception as e:
        print(f"Erreur dans main: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nArrêt du système")
    except Exception as e:
        print(f"Erreur fatale: {e}")