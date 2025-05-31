#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py

Aplicación Flask que implementa la simulación de “Puestos de Carga – Festival Río Vivo”
(punto B del TP4), con parámetros ingresables desde el frontend:
  - Tiempo máximo de simulación (T_max, en minutos).
  - Cantidad máxima de eventos (N_max).
  - Media de interarribos (en minutos) – por defecto 13.
  - Porcentaje de cada tipo de cargador: USB-C (0.45), Lightning (0.25), MicroUSB (0.30).
  - Tiempo de validación (en minutos) tras terminar la carga – por defecto 2.

El vector de estado final consta de 19 columnas en cada fila:
  1. Iteraciones
  2. Evento (“Llegada dispositivo”, “Fin de carga”, “Validación”)
  3. RND dispositivo
  4. Tipo dispositivo
  5. RND tiempo
  6. Tiempo entre llegadas
  7. Próxima llegada
  8. Cant dispositivos en puerto
  9. Porcentaje Puestos en uso
  10. RND carga
  11. Tiempo carga
  12. Fin de carga puesto 1
  13. Fin de carga puesto 2
  14. Fin de carga puesto 3
  15. Fin de carga puesto 4
  16. Fin de carga puesto 5
  17. Fin de carga puesto 6
  18. Fin de carga puesto 7
  19. Fin de carga puesto 8

Para ejecutar:
  - Guardar este archivo en el mismo nivel que la carpeta `templates`.
  - Instalar Flask: `pip install flask`
  - Ejecutar: `python app.py`
  - Abrir en el navegador: http://localhost:5000/
"""

import math
import random
import heapq
from flask import Flask, render_template, request

app = Flask(__name__)


class Evento:
    """
    Representa un evento en la simulación:
      - tiempo: instante en minutos (float)
      - tipo: "arrival", "end_charge" o "end_validation"
      - data: información adicional:
           * para end_charge y end_validation: (idx_servidor, tipo_dispositivo)
    """
    _contador_global = 0

    def __init__(self, tiempo, tipo, data=None):
        self.tiempo = tiempo
        self.tipo = tipo
        self.data = data
        # Para evitar empates en el heap, asignamos un orden secuencial
        self._orden = Evento._contador_global
        Evento._contador_global += 1

    def __lt__(self, otro):
        # Orden primero por tiempo, luego por orden de creación
        if self.tiempo == otro.tiempo:
            return self._orden < otro._orden
        return self.tiempo < otro.tiempo


def generar_interarribo(media):
    """
    Retorna un interarribo (en minutos) ~ Exp(media).
    """
    u = random.random()
    return -media * math.log(1 - u)


def seleccionar_tiempo_carga():
    """
    Retorna (carga_horas, u_tiempo) con distribución:
      P(1h)=0.50, P(2h)=0.30, P(3h)=0.15, P(4h)=0.05.
    """
    u = random.random()
    if u < 0.50:
        return 1, u
    elif u < 0.80:
        return 2, u
    elif u < 0.95:
        return 3, u
    else:
        return 4, u


def simular_puestos_carga(
    T_max,
    N_max,
    media_interarribo,
    p_usb_c,
    p_lightning,
    p_microusb,
    tiempo_validacion
):
    """
    Ejecuta la simulación con los parámetros indicados.  
    Devuelve:
      - vector_estado: lista de 19-columnas (cada fila es un dict).
      - resumen: dict con n_aceptadas, n_rechazadas, recaudacion_total, utilizacion_promedio.
      - ultima_fila: dict con las 19 columnas de la última iteración.
    """
    random.seed()  # semilla aleatoria

    # 1) Parámetros fijos
    n_servidores = 8
    tarifas = {"USB-C": 300, "Lightning": 500, "MicroUSB": 1000}  # $/hora

    # 2) Estado de cada servidor: 
    #    "ocupado" (bool), "device_type" (str), "etapa" ("cargando"/"validando"/None), 
    #    "fin_carga" (float o None)
    servidores = [
        {"ocupado": False, "device_type": None, "etapa": None, "fin_carga": None}
        for _ in range(n_servidores)
    ]

    # 3) Cola de eventos futuros (heap)
    eventos_futuros = []

    # Programar la primera llegada
    primer_inter = generar_interarribo(media_interarribo)
    heapq.heappush(eventos_futuros, Evento(primer_inter, "arrival"))

    # 4) Variables de conteo
    clock = 0.0
    evento_id = 0
    n_aceptadas = 0
    n_rechazadas = 0
    recaudacion_total = 0.0

    # Para cálculo de área bajo número de servidores ocupados
    area_ocupados = 0.0
    reloj_previo = 0.0
    n_ocupados_previo = 0

    # 5) Vector de estado: fila por cada evento, con 19 columnas
    vector_estado = []

    # 6) Bucle principal: procesar hasta T_max o N_max eventos
    while eventos_futuros and evento_id < N_max:
        evento = heapq.heappop(eventos_futuros)
        t_evt = evento.tiempo

        if t_evt > T_max:
            break

        # Avanzar reloj
        clock = t_evt

        # Actualizar área bajo la curva
        delta_t = clock - reloj_previo
        area_ocupados += delta_t * n_ocupados_previo
        reloj_previo = clock

        # Contador de iteraciones
        evento_id += 1

        # Array base con 19 campos en el orden especificado
        fila = {
            "Iteraciones": evento_id,
            "Evento": None,
            "RND dispositivo": None,
            "Tipo dispositivo": None,
            "RND tiempo": None,
            "Tiempo entre llegadas": None,
            "Próxima llegada": None,
            "Cant dispositivos en puerto": None,
            "Porcentaje Puestos en uso": None,
            "RND carga": None,
            "Tiempo carga": None,
            # Inicializamos todas las 8 columnas de fin_carga en None
            **{f"Fin de carga puesto {i+1}": None for i in range(n_servidores)}
        }

        # ==== Caso 1: Llegada de dispositivo ====
        if evento.tipo == "arrival":
            # 1. Elegir tipo de dispositivo con RND dispositivo
            u_device = random.random()
            if u_device < p_usb_c:
                tipo_disp = "USB-C"
            elif u_device < p_usb_c + p_lightning:
                tipo_disp = "Lightning"
            else:
                tipo_disp = "MicroUSB"

            # 2. Generar interarribo exponencial con RND tiempo
            u_tiempo = random.random()
            interarribo = -media_interarribo * math.log(1 - u_tiempo)
            prox_llegada = clock + interarribo

            # 3. Llenar columnas de llegada
            fila["Evento"] = "Llegada dispositivo"
            fila["RND dispositivo"] = round(u_device, 4)
            fila["Tipo dispositivo"] = tipo_disp
            fila["RND tiempo"] = round(u_tiempo, 4)
            fila["Tiempo entre llegadas"] = round(interarribo, 4)
            fila["Próxima llegada"] = round(prox_llegada, 4)

            # 4. Intentar ocupar un servidor libre
            idx_libres = [i for i, srv in enumerate(servidores) if not srv["ocupado"]]
            if idx_libres:
                idx_ser = idx_libres[0]
                servidores[idx_ser]["ocupado"] = True
                servidores[idx_ser]["device_type"] = tipo_disp
                servidores[idx_ser]["etapa"] = "cargando"

                # Generar duración de carga con RND carga
                carga_horas, u_tiempo_carga = seleccionar_tiempo_carga()
                dur_carga_min = carga_horas * 60
                t_fin_carga = clock + dur_carga_min

                # Registrar en el servidor su próximo fin de carga
                servidores[idx_ser]["fin_carga"] = t_fin_carga

                # Acumular recaudación
                recaudacion_total += tarifas[tipo_disp] * carga_horas

                # Programar evento de fin de carga
                data_carga = (idx_ser, tipo_disp)
                heapq.heappush(eventos_futuros, Evento(t_fin_carga, "end_charge", data_carga))

                # Llenar columnas de RND carga y Tiempo carga
                fila["RND carga"] = round(u_tiempo_carga, 4)
                fila["Tiempo carga"] = int(dur_carga_min)

                n_aceptadas += 1
            else:
                # Rechazo la llegada
                n_rechazadas += 1

            # 5. Siempre programar la próxima llegada
            heapq.heappush(eventos_futuros, Evento(prox_llegada, "arrival"))

        # ==== Caso 2: Fin de carga ====
        elif evento.tipo == "end_charge":
            idx_ser, tipo_disp = evento.data
            # Cambiar etapa a validación
            servidores[idx_ser]["etapa"] = "validando"
            # Borrar fin_carga porque ya terminó la carga
            servidores[idx_ser]["fin_carga"] = None

            # Programar fin de validación
            t_fin_valid = clock + tiempo_validacion
            data_valid = (idx_ser, tipo_disp)
            heapq.heappush(eventos_futuros, Evento(t_fin_valid, "end_validation", data_valid))

            fila["Evento"] = "Fin de carga"
            fila["Tipo dispositivo"] = tipo_disp
            # Para este evento, las columnas de RND y tiempos de llegada no aplican (ya se gestionaron en la llegada)
            # Dejamos RND carga / Tiempo carga en None
            # "Próxima llegada" ya está programada en la cola, así que dejamos None aquí

        # ==== Caso 3: Fin de validación ====
        elif evento.tipo == "end_validation":
            idx_ser, tipo_disp = evento.data
            # Liberar servidor
            servidores[idx_ser]["ocupado"] = False
            servidores[idx_ser]["device_type"] = None
            servidores[idx_ser]["etapa"] = None
            servidores[idx_ser]["fin_carga"] = None

            fila["Evento"] = "Validación"
            fila["Tipo dispositivo"] = tipo_disp
            # RND y tiempos no aplican en validación
            # "Próxima llegada" ya programada, dejamos None

        else:
            # No debería ocurrir
            continue

        # 6. Después de procesar el evento, contamos dispositivos ocupados
        ocupados = sum(1 for srv in servidores if srv["ocupado"])
        fila["Cant dispositivos en puerto"] = ocupados
        fila["Porcentaje Puestos en uso"] = round((ocupados / n_servidores) * 100, 2)

        # 7. Finalmente, llenamos las columnas 12–19 con fin_carga de cada servidor
        for i in range(n_servidores):
            key = f"Fin de carga puesto {i+1}"
            fin_carga_i = servidores[i]["fin_carga"]
            fila[key] = round(fin_carga_i, 4) if fin_carga_i is not None else None

        # 8. Agregar la fila completa (19 columnas) al vector de estado
        vector_estado.append(fila)

        # Actualizar n_ocupados_previo para el próximo loop
        n_ocupados_previo = ocupados

    # Ajuste de área en caso de que clock < T_max
    if clock < T_max:
        delta_t = T_max - reloj_previo
        area_ocupados += delta_t * n_ocupados_previo
        clock_para_util = T_max
    else:
        clock_para_util = clock

    # Cálculo de Utilización promedio (%)
    utilizacion_promedio = (
        area_ocupados / (n_servidores * clock_para_util) * 100
        if clock_para_util > 0 else 0.0
    )

    resumen = {
        "n_aceptadas": n_aceptadas,
        "n_rechazadas": n_rechazadas,
        "recaudacion_total": round(recaudacion_total, 2),
        "utilizacion_promedio": round(utilizacion_promedio, 2)
    }

    ultima_fila = vector_estado[-1] if vector_estado else None
    return vector_estado, resumen, ultima_fila


# === RUTAS DE FLASK ===

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        error_msg = None
        try:
            T_max = float(request.form.get("T_max", "0"))
            N_max = int(request.form.get("N_max", "0"))

            # Valores por defecto si está vacío
            media_interarribo = float(request.form.get("media_interarribo", "13"))
            tiempo_validacion = float(request.form.get("tiempo_validacion", "2"))

            p_usb_c = float(request.form.get("p_usb_c", "0.45"))
            p_lightning = float(request.form.get("p_lightning", "0.25"))
            p_microusb = float(request.form.get("p_microusb", "0.30"))

            suma_probs = p_usb_c + p_lightning + p_microusb
            if abs(suma_probs - 1.0) > 1e-6:
                error_msg = "Los porcentajes de USB-C, Lightning y MicroUSB deben sumar 1.0."
        except ValueError:
            error_msg = "Por favor, ingrese valores numéricos válidos en todos los campos."

        if error_msg:
            return render_template(
                "index.html",
                error=error_msg,
                resumen=None,
                ultima_fila=None,
                vector_estado=None
            )

        # Ejecutar simulación
        vector, resumen, ultima_fila = simular_puestos_carga(
            T_max=T_max,
            N_max=N_max,
            media_interarribo=media_interarribo,
            p_usb_c=p_usb_c,
            p_lightning=p_lightning,
            p_microusb=p_microusb,
            tiempo_validacion=tiempo_validacion
        )

        if not vector:
            return render_template(
                "index.html",
                error="La simulación no produjo ningún evento (revisa los parámetros).",
                resumen=None,
                ultima_fila=None,
                vector_estado=None
            )

        return render_template(
            "index.html",
            error=None,
            resumen=resumen,
            ultima_fila=ultima_fila,
            vector_estado=vector
        )

    # GET → formulario con valores por defecto
    return render_template("index.html",
                           error=None,
                           resumen=None,
                           ultima_fila=None,
                           vector_estado=None)


if __name__ == "__main__":
    app.run(debug=True)
