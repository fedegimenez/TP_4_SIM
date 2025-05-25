from flask import Flask, render_template, request
import random
import heapq
import math

app = Flask(__name__)

def simulate(X_hours, max_iter, j_time, i_count, n_servers):
    # Convertir horas a minutos
    X = X_hours * 60
    # Tarifas por hora
    rates = {'USB-C':300, 'Lightning':500, 'MicroUSB':1000}
    # Opciones y pesos para tipo de cargador
    type_options = ['USB-C', 'Lightning', 'MicroUSB']
    type_weights = [0.45, 0.25, 0.30]
    # Opciones y pesos para tiempo de carga (horas)
    service_options = [1, 2, 3, 4]
    service_weights = [0.5, 0.3, 0.15, 0.05]
    # Inicializar servidores
    servers = [{'id': i, 'busy': False, 'end_time': None} for i in range(n_servers)]
    # Lista de eventos: (tiempo, secuencia, tipo, id_servidor)
    event_list = []
    seq = 0
    # Programar primera llegada
    U1 = random.random()
    inter = -math.log(U1) * 13
    next_arrival = inter
    heapq.heappush(event_list, (next_arrival, seq, 'arrival', None))
    seq += 1
    current_time = 0
    records = []
    # Variables auxiliares
    served = {'USB-C': 0, 'Lightning': 0, 'MicroUSB': 0}
    drop = 0
    revenue = 0.0
    last_U1 = last_U2 = last_U3 = None
    iter_count = 0

    while event_list and iter_count < max_iter:
        time, _, ev_type, srv_id = heapq.heappop(event_list)
        if time > X:
            break
        current_time = time
        iter_count += 1

        # Próximos eventos
        upcoming = list(event_list)
        next_arrival_time = next((t for t, _, et, _ in upcoming if et == 'arrival'), None)
        next_departures = sorted([t for t, _, et, _ in upcoming if et == 'departure'])

        # Procesar evento
        if ev_type == 'arrival':
            last_U1 = U1
            # Servidor libre?
            free_srv = next((s for s in servers if not s['busy']), None)
            if free_srv:
                # Generar tiempo de carga
                U2 = random.random()
                last_U2 = U2
                service_hours = random.choices(service_options, weights=service_weights)[0]
                # Generar tipo de usuario
                U3 = random.random()
                last_U3 = U3
                cust_type = random.choices(type_options, weights=type_weights)[0]
                # Duración total (carga + validación)
                service_minutes = service_hours * 60 + 2
                # Programar salida
                end_t = current_time + service_minutes
                free_srv['busy'] = True
                free_srv['end_time'] = end_t
                heapq.heappush(event_list, (end_t, seq, 'departure', free_srv['id']))
                seq += 1
                # Actualizar estadísticas
                served[cust_type] += 1
                revenue += service_hours * rates[cust_type]
            else:
                drop += 1
            # Programar próxima llegada
            U1 = random.random()
            inter = -math.log(U1) * 13
            next_arrival = current_time + inter
            heapq.heappush(event_list, (next_arrival, seq, 'arrival', None))
            seq += 1

        elif ev_type == 'departure':
            srv = next(s for s in servers if s['id'] == srv_id)
            srv['busy'] = False
            srv['end_time'] = None

        # Registrar estado
        records.append({
            'time': round(current_time / 60, 4),  # en horas
            'event': ev_type,
            'next_arrival': round(next_arrival_time / 60, 4) if next_arrival_time else None,
            'next_departures': [round(t / 60, 4) for t in next_departures],
            'servers': [
                {'id': s['id'], 'busy': s['busy'], 'remaining': round((s['end_time'] - current_time) / 60, 4) if s['busy'] else 0}
                for s in servers
            ],
            'served': served.copy(),
            'drop': drop,
            'revenue': round(revenue, 2),
            'U_interarrival': round(last_U1, 4) if last_U1 else None,
            'U_service': round(last_U2, 4) if last_U2 else None,
            'U_type': round(last_U3, 4) if last_U3 else None
        })

    # Seleccionar filas desde time >= j_time
    start_idx = next((i for i, rec in enumerate(records) if rec['time'] >= j_time), 0)
    selected = records[start_idx:start_idx + i_count]
    last = records[-1] if records else {}
    return selected, last

@app.route('/', methods=['GET', 'POST'])
def index():
    results = []
    last = {}
    params = {}
    if request.method == 'POST':
        X = float(request.form['X'])
        max_iter = int(request.form['max_iter'])
        j = float(request.form['j'])
        i = int(request.form['i'])
        servers = int(request.form['servers'])
        results, last = simulate(X, max_iter, j, i, servers)
        params = {'X': X, 'max_iter': max_iter, 'j': j, 'i': i, 'servers': servers}
    return render_template('index.html', results=results, last=last, params=params)

if __name__ == '__main__':
    app.run(debug=True)