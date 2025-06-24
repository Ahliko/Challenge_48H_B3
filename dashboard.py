import paho.mqtt.client as mqtt
import dash
from dash import html, dcc
from dash.dependencies import Input, Output
import time
from threading import Thread

MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_TOPIC = "maison/porte/etat"

etat_porte = "Inconnu"
derniere_mise_a_jour = "Jamais"

def on_connect(client, userdata, flags, rc):
    client.subscribe(MQTT_TOPIC)

def on_message(client, userdata, msg):
    global etat_porte, derniere_mise_a_jour
    payload = msg.payload.decode()
    etat_porte = payload
    derniere_mise_a_jour = time.strftime("%H:%M:%S")

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

def mqtt_loop():
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_forever()

mqtt_thread = Thread(target=mqtt_loop, daemon=True)
mqtt_thread.start()

app = dash.Dash(__name__, title="Dashboard Système de Sécurité")

app.layout = html.Div([
    html.H1("Système de Surveillance de Porte",
            style={'textAlign': 'center', 'color': '#2c3e50', 'marginBottom': '30px'}),

    html.Div([
        html.Div([
            html.H3("État de la Porte", style={'color': '#34495e'}),
            html.Div(id="etat-porte", style={
                'fontSize': '28px',
                'fontWeight': 'bold',
                'padding': '25px',
                'border': '2px solid #bdc3c7',
                'borderRadius': '10px',
                'marginBottom': '25px',
                'textAlign': 'center'
            }),

            html.Div([
                html.Div([
                    html.H4("État de l'Alarme", style={'color': '#34495e', 'marginBottom': '10px'}),
                    html.Div(id="etat-alarme", style={
                        'fontSize': '20px',
                        'fontWeight': 'bold',
                        'padding': '15px',
                        'border': '1px solid #bdc3c7',
                        'borderRadius': '8px',
                        'textAlign': 'center'
                    })
                ], style={'width': '48%', 'display': 'inline-block'}),

                html.Div([
                    html.H4("Statut Système", style={'color': '#34495e', 'marginBottom': '10px'}),
                    html.Div(id="statut-systeme", style={
                        'fontSize': '18px',
                        'padding': '15px',
                        'border': '1px solid #bdc3c7',
                        'borderRadius': '8px',
                        'textAlign': 'center'
                    })
                ], style={'width': '48%', 'display': 'inline-block', 'marginLeft': '4%'})
            ], style={'marginBottom': '25px'}),

            html.Div([
                html.Span("Dernière mise à jour: ", style={'fontWeight': 'bold'}),
                html.Span(id="derniere-maj", style={'color': '#7f8c8d'})
            ], style={'textAlign': 'center', 'fontSize': '16px'}),

            html.Div([
                html.H4("Historique des États", style={'color': '#34495e', 'marginTop': '30px'}),
                html.Div(id="historique", style={
                    'maxHeight': '200px',
                    'overflowY': 'auto',
                    'border': '1px solid #bdc3c7',
                    'borderRadius': '8px',
                    'padding': '10px',
                    'backgroundColor': '#f8f9fa'
                })
            ]),

            html.Div([
                dcc.Interval(
                    id='interval-component',
                    interval=1*1000,
                    n_intervals=0
                )
            ])
        ], style={
            'width': '90%',
            'maxWidth': '800px',
            'margin': 'auto',
            'padding': '30px',
            'boxShadow': '0px 0px 20px rgba(0,0,0,0.1)',
            'borderRadius': '15px',
            'backgroundColor': 'white'
        })
    ], style={'backgroundColor': '#ecf0f1', 'minHeight': '100vh', 'padding': '20px'})
])

historique_etats = []

def analyser_etat(etat_complet):
    parties = etat_complet.split(" - ")

    etat_porte_seul = parties[0] if parties else "Inconnu"

    alarme_status = "OFF"
    statut_special = ""

    for partie in parties[1:] if len(parties) > 1 else []:
        if "Alarme:" in partie:
            alarme_status = "ON" if "ON" in partie else "OFF"
        elif "ALERTE!" in partie:
            statut_special = "🚨 ALERTE INTRUSION!"
        elif "Saisie code" in partie:
            statut_special = "🔢 Saisie de code en cours..."
        elif "demarrage" in partie.lower() or "démarré" in partie.lower():
            statut_special = "🔄 Système démarré"

    return etat_porte_seul, alarme_status, statut_special

@app.callback(
    [Output('etat-porte', 'children'),
     Output('etat-porte', 'style'),
     Output('etat-alarme', 'children'),
     Output('etat-alarme', 'style'),
     Output('statut-systeme', 'children'),
     Output('historique', 'children'),
     Output('derniere-maj', 'children')],
    [Input('interval-component', 'n_intervals')]
)
def update_dashboard(n):
    global historique_etats

    etat_porte_seul, alarme_status, statut_special = analyser_etat(etat_porte)

    style_porte = {
        'fontSize': '28px',
        'fontWeight': 'bold',
        'padding': '25px',
        'border': '2px solid #bdc3c7',
        'borderRadius': '10px',
        'marginBottom': '25px',
        'textAlign': 'center'
    }

    if "alerte" in etat_porte.lower():
        style_porte['backgroundColor'] = '#e74c3c'
        style_porte['color'] = 'white'
        style_porte['border'] = '2px solid #c0392b'
        style_porte['animation'] = 'blink 1s infinite'
        etat_affiche = f"🚨 {etat_porte_seul} - ALERTE!"
    elif etat_porte_seul.lower() == "ouverte":
        style_porte['backgroundColor'] = '#e67e22'
        style_porte['color'] = 'white'
        etat_affiche = f"🔓 {etat_porte_seul}"
    elif etat_porte_seul.lower() == "fermée" or etat_porte_seul.lower() == "fermé":
        style_porte['backgroundColor'] = '#27ae60'
        style_porte['color'] = 'white'
        etat_affiche = f"🔒 {etat_porte_seul}"
    else:
        style_porte['backgroundColor'] = '#95a5a6'
        style_porte['color'] = 'white'
        etat_affiche = f"❓ {etat_porte_seul}"

    style_alarme = {
        'fontSize': '20px',
        'fontWeight': 'bold',
        'padding': '15px',
        'border': '1px solid #bdc3c7',
        'borderRadius': '8px',
        'textAlign': 'center'
    }

    if alarme_status == "ON":
        style_alarme['backgroundColor'] = '#e74c3c'
        style_alarme['color'] = 'white'
        alarme_affichee = "🔴 ACTIVÉE"
    else:
        style_alarme['backgroundColor'] = '#95a5a6'
        style_alarme['color'] = 'white'
        alarme_affichee = "⚪ DÉSACTIVÉE"

    if statut_special == "":
        statut_special = "✅ Fonctionnement normal"

    if len(historique_etats) == 0 or historique_etats[-1]['etat'] != etat_porte:
        historique_etats.append({
            'etat': etat_porte,
            'heure': time.strftime("%H:%M:%S")
        })
        if len(historique_etats) > 10:
            historique_etats.pop(0)

    historique_html = []
    for i, entry in enumerate(reversed(historique_etats)):
        couleur = '#27ae60' if 'fermée' in entry['etat'].lower() or 'fermé' in entry['etat'].lower() else '#e67e22'
        if 'alerte' in entry['etat'].lower():
            couleur = '#e74c3c'

        historique_html.append(
            html.Div([
                html.Span(f"{entry['heure']}: ", style={'fontWeight': 'bold'}),
                html.Span(entry['etat'], style={'color': couleur})
            ], style={'marginBottom': '5px', 'padding': '5px', 'borderBottom': '1px solid #ecf0f1'})
        )

    return (etat_affiche, style_porte, alarme_affichee, style_alarme,
            statut_special, historique_html, derniere_mise_a_jour)

if __name__ == '__main__':
    app.run(debug=True)