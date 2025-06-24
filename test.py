from machine import ADC, Pin, unique_id, Timer
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
intrusion_detectee = False  # Nouvelle variable pour l'état d'intrusion
code_alarme = "1234"
temps_ouverture = 0
delai_alerte = 10
saisie_code_en_cours = False
code_saisi = ""

buzzer = Buzzer(13)
pave = Pave(buzzer=buzzer)

# Variables pour les timers et interruptions
timer_alerte = Timer(0)
timer_buzzer = Timer(1)
timer_led = Timer(2)
timer_adc = Timer(3)

led_alerte_state = False
buzzer_alerte_state = False
buzzer_pattern_step = 0

def interrupt_lecture_porte(timer):
    global etat_porte
    try:
        valeur = adc.read()
        if valeur > 3500:
            etat_porte = "Fermée"
        else:
            etat_porte = "Ouverte"
    except:
        pass

def interrupt_led_alerte(timer):
    global led_alerte_state
    if alarme_en_alerte or intrusion_detectee:
        led_alerte_state = not led_alerte_state
        led_rouge.value(led_alerte_state)

def interrupt_buzzer_alerte(timer):
    global buzzer_alerte_state, buzzer_pattern_step
    if alarme_en_alerte or intrusion_detectee:
        if buzzer_pattern_step == 0:
            buzzer.freq = 2000
            buzzer._Buzzer__on()
            buzzer_pattern_step = 1
        elif buzzer_pattern_step == 1:
            buzzer._Buzzer__off()
            buzzer_pattern_step = 2
        elif buzzer_pattern_step == 2:
            buzzer.freq = 1800
            buzzer._Buzzer__on()
            buzzer_pattern_step = 3
        else:
            buzzer._Buzzer__off()
            buzzer_pattern_step = 0

def interrupt_timeout_alerte(timer):
    global alarme_en_alerte, intrusion_detectee
    if alarme_activee and etat_porte == "Ouverte":
        alarme_en_alerte = True
        intrusion_detectee = True
        print("🚨 ALERTE ! Intrusion détectée - L'alarme continuera même si la porte se ferme !")
        timer_led.init(period=100, mode=Timer.PERIODIC, callback=interrupt_led_alerte)
        timer_buzzer.init(period=150, mode=Timer.PERIODIC, callback=interrupt_buzzer_alerte)

def demarrer_alerte_imminente():
    print("⚠️ Porte ouverte - Vous avez 10 secondes pour la fermer !")
    timer_alerte.init(period=delai_alerte*1000, mode=Timer.ONE_SHOT, callback=interrupt_timeout_alerte)

def arreter_alerte_sans_intrusion():
    """Arrête l'alerte seulement si aucune intrusion n'a été détectée"""
    global alarme_en_alerte
    if not intrusion_detectee:
        alarme_en_alerte = False
        timer_alerte.deinit()
        timer_led.deinit()
        timer_buzzer.deinit()
        led_rouge.value(0)
        buzzer._Buzzer__off()
        print("✅ Porte fermée à temps - Alerte annulée")

def arreter_alerte_complete():
    """Arrête complètement l'alerte (utilisé lors de la désactivation de l'alarme)"""
    global alarme_en_alerte, intrusion_detectee, buzzer_pattern_step
    alarme_en_alerte = False
    intrusion_detectee = False
    buzzer_pattern_step = 0
    timer_alerte.deinit()
    timer_led.deinit()
    timer_buzzer.deinit()
    led_rouge.value(0)
    buzzer._Buzzer__off()

timer_adc.init(period=100, mode=Timer.PERIODIC, callback=interrupt_lecture_porte)

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

async def gerer_alarme():
    global alarme_activee, temps_ouverture
    etat_precedent = etat_porte

    while True:
        # Démarrage du délai d'alerte lors de l'ouverture
        if alarme_activee and etat_porte == "Ouverte" and etat_precedent == "Fermée" and not alarme_en_alerte and not intrusion_detectee:
            temps_ouverture = time.time()
            asyncio.create_task(son_alerte_imminente())
            demarrer_alerte_imminente()

        # Annulation de l'alerte SEULEMENT si aucune intrusion n'a été détectée
        elif etat_porte == "Fermée" and etat_precedent == "Ouverte" and alarme_activee:
            if not intrusion_detectee:
                arreter_alerte_sans_intrusion()
                temps_ouverture = 0
            else:
                print("⚠️ Porte fermée mais intrusion détectée - L'alarme continue !")

        etat_precedent = etat_porte
        await asyncio.sleep_ms(200)

async def gerer_pave():
    global alarme_activee, code_alarme, saisie_code_en_cours, code_saisi

    while True:
        try:
            touche = await pave.getkey()

            if touche is not None:
                print(f"Touche pressée: {touche}")

                if touche == 'F' and not saisie_code_en_cours:
                    if not alarme_activee:
                        alarme_activee = True
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
                        await clignoter_led(led_verte, 1, 150)
                    elif saisie_code_en_cours:
                        code_saisi += touche
                        print(f"Saisie du code: {'*' * len(code_saisi)}")
                        await clignoter_led(led_verte, 1, 150)

                        if len(code_saisi) >= 4:
                            if code_saisi == code_alarme:
                                alarme_activee = False
                                saisie_code_en_cours = False
                                arreter_alerte_complete()  # Arrête complètement l'alerte
                                print("🔓 Alarme DÉSACTIVÉE - Système réinitialisé")
                                await clignoter_led(led_verte, 5, 100)
                                await son_desactivation()
                            else:
                                print("❌ Code incorrect!")
                                saisie_code_en_cours = False
                                await clignoter_led(led_rouge, 3, 200)
                                buzzer.freq = 300
                                await buzzer.beep(0.5)
                            code_saisi = ""

                elif touche == 'C' and saisie_code_en_cours:
                    saisie_code_en_cours = False
                    code_saisi = ""
                    print("Saisie annulée")

                elif touche == 'E' and saisie_code_en_cours:
                    if code_saisi == code_alarme:
                        alarme_activee = False
                        saisie_code_en_cours = False
                        arreter_alerte_complete()  # Arrête complètement l'alerte
                        print("🔓 Alarme DÉSACTIVÉE - Système réinitialisé")
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

async def surveiller_mqtt():
    global dernier_etat_publie, mqtt_client

    while True:
        try:
            # Gestion des LEDs (sauf pendant l'alerte)
            if not alarme_en_alerte and not intrusion_detectee:
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
                        if intrusion_detectee:
                            etat_complet += " - INTRUSION DÉTECTÉE!"
                        elif alarme_en_alerte:
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
                print(etat_complet)
                print(f"Erreur MQTT: {e}")
                mqtt_client = connecter_mqtt()

            gc.collect()
            await asyncio.sleep_ms(500)

        except Exception as e:
            print(f"Erreur surveillance: {e}")
            await asyncio.sleep_ms(1000)

async def main():
    global mqtt_client

    print("=== Système de surveillance avec alarme ===")
    print("Comportement de l'alarme:")
    print("- Délai de 10s pour fermer la porte avant alerte")
    print("- Si intrusion détectée, l'alarme continue même porte fermée")
    print("- Seul le code correct peut arrêter l'alarme après intrusion")
    print()
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
            surveiller_mqtt(),
            gerer_pave(),
            gerer_alarme()
        )
    except Exception as e:
        print(f"Erreur dans main: {e}")
    finally:
        timer_adc.deinit()
        timer_alerte.deinit()
        timer_led.deinit()
        timer_buzzer.deinit()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nArrêt du système")
    except Exception as e:
        print(f"Erreur fatale: {e}")