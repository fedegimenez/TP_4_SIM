#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py

Aplicación Flask que implementa la simulación de “Puestos de Carga – Festival Río Vivo”
(punto B del TP4), con los siguientes puntos clave:

  • Se agrega la columna “Reloj” como columna 2, inmediatamente después de “Iteraciones”.  
    – En la fila 0 (“INICIO SIM”), Reloj = 0.  
    – En cada evento, Reloj = tiempo del evento.

  • El vector de estado final consta ahora de **30 columnas** en cada fila, en este orden:

    1. Iteraciones
    2. Reloj
    3. Evento
    4. RND dispositivo
    5. Tipo dispositivo
    6. RND tiempo
    7. Tiempo entre llegadas
    8. Próxima llegada
    9. Cant dispositivos en puerto
   10. Porcentaje Puestos en uso
   11. RND carga
   12. Tiempo carga
   13. Fin de carga puesto 1
   14. Fin de carga puesto 2
   15. Fin de carga puesto 3
   16. Fin de carga puesto 4
   17. Fin de carga puesto 5
   18. Fin de carga puesto 6
   19. Fin de carga puesto 7
   20. Fin de carga puesto 8
   21. Estados puestos de validación
   22. Cola de validación
   23. Tiempo validación
   24. Fin de validación
   25. Acumulador tiempo USB C
   26. Acumulador tiempo Lightning
   27. Acumulador tiempo MicroUSB
   28. Recaudación USB C
   29. Recaudación Lightning
   30. Recaudación MicroUSB

Para ejecutar:
  1. Instalar Flask si no lo tienes:  `pip install flask`
  2. Guardar este archivo junto a la carpeta `templates/`
  3. Ejecutar: `python app.py`
  4. Abrir en el navegador: http://localhost:5000/
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
      - data: para end_charge y end_validation → (idx_servidor, tipo_dispositivo, fin_carga_o_fin_validación)
    """
    _contador_global = 0

    def __init__(self, tiempo, tipo, data=None):
        self.tiempo = tiempo
        self.tipo = tipo
        self.data = data
        # Para deshacer empates en el heap, asignamos un orden secuencial
        self._orden = Evento._contador_global
        Evento._contador_global += 1

    def __lt__(self, otro):
        # Orden primero por tiempo; si empatan, por orden de creación
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
    Retorna (carga_horas, u_tiempo) con distribución discreta:
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
    tiempo_validacion,
    n_servidores
):
    """
    Ejecuta la simulación y devuelve:
      - vector_estado: lista de 30 columnas (cada fila es un dict).
      - resumen: dict con n_aceptadas, n_rechazadas, recaudacion_total, utilizacion_promedio.
      - ultima_fila: dict con las 30 columnas de la última iteración.
    """

    random.seed()  # semilla aleatoria

    # ===== Parámetros fijos =====
    tarifas = {"USB-C": 300, "Lightning": 500, "MicroUSB": 1000}  # $/hora
    puesto_validacion_libre = True
    cola_validacion = []

    # Estado de cada servidor:
    #   "ocupado" (bool),
    #   "device_type" (str),
    #   "etapa" ("cargando"/"validando"/None),
    #   "fin_carga" (float o None),
    #   "fin_validacion" (float o None)
    servidores = [
        {"ocupado": False, "device_type": None, "etapa": None,
         "fin_carga": None, "fin_validacion": None, "duracion_carga": None}
        for _ in range(n_servidores)
    ]

    # Cola de eventos futuros (heap)
    eventos_futuros = []

    # ===== Crear fila 0: INICIO SIM =====
    # Generar RND tiempo para primera llegada
    u_tiempo0 = random.random()
    interarribo0 = -media_interarribo * math.log(1 - u_tiempo0)
    prox_llegada0 = interarribo0

    fila0 = {
        "Iteraciones": 0,
        "Reloj": 0.0,
        "Evento": "INICIO SIM",
        "RND dispositivo": None,
        "Tipo dispositivo": None,
        "RND tiempo": round(u_tiempo0, 4),
        "Tiempo entre llegadas": round(interarribo0, 4),
        "Próxima llegada": round(prox_llegada0, 4),
        "Cant dispositivos en puerto": 0,
        "Porcentaje Puestos en uso": 0.0,
        "Acum porcentaje puestos en uso": 0.0,
        "Promedio porcentaje puestos en uso": 0.0,
        "RND carga": None,
        "Tiempo carga": None,
    }
    # Columnas 13–20 (Fin de carga puesto 1..8)
    for i in range(n_servidores):
        fila0[f"Fin de carga puesto {i+1}"] = None
        fila0[f"Tiempo carga puesto {i+1}"] = None
    # Columnas 21–30
    fila0["Estado puesto de validación"] = "Libre"
    fila0["Cola de validación"] = 0
    fila0["Tiempo validación"] = 0
    fila0["Fin de validación"] = None
    fila0["Acumulador tiempo USB C"] = 0
    fila0["Acumulador tiempo Lightning"] = 0
    fila0["Acumulador tiempo MicroUSB"] = 0
    fila0["Recaudación USB C"] = 0.0
    fila0["Recaudación Lightning"] = 0.0
    fila0["Recaudación MicroUSB"] = 0.0
    fila0["Recaudacion Total"] = 0.0
    fila0["Acumulador Dispositivos Aceptados"] = 0.0
    fila0["Acumulador Dispositivos Rechazados"] = 0.0
    


    # Inicializar vector de estado con esa fila 0
    vector_estado = [fila0]

    # ===== Programar la primera llegada usando prox_llegada0 =====
    heapq.heappush(eventos_futuros, Evento(prox_llegada0, "arrival"))

    # ===== Variables acumuladas =====
    clock = 0.0
    evento_id = 0
    n_aceptadas = 0
    n_rechazadas = 0
    recaudacion_total = 0.0

    acum_porcentaje_puestos = 0.0

    acum_time_usb_c = 0
    acum_time_lightning = 0
    acum_time_microusb = 0

    rec_usb_c = 0.0
    rec_lightning = 0.0
    rec_microusb = 0.0

    # Para cálculo de área de utilización
    area_ocupados = 0.0
    reloj_previo = 0.0
    n_ocupados_previo = 0
    acum_porcentaje_ponderado = 0.0
    acum_tiempo_ponderado = 0.0

    # ===== Bucle de eventos (filas 1, 2, 3…) =====
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

        # Nuevo contador de iteración
        evento_id += 1

        # Crear fila base con las 30 columnas inicializadas
        fila = {
            "Iteraciones": evento_id,
            "Reloj": round(clock, 4),
            "Evento": None,
            "RND dispositivo": None,
            "Tipo dispositivo": None,
            "RND tiempo": None,
            "Tiempo entre llegadas": None,
            "Próxima llegada": None,
            "Cant dispositivos en puerto": None,
            "Porcentaje Puestos en uso": None,
            "Acum porcentaje puestos en uso": None,
            "Promedio porcentaje puestos en uso": None,
            "RND carga": None,
            "Tiempo carga": None,
        }
        # Columnas 13–20: Fin de carga puesto 1..8
        for i in range(n_servidores):
            fila[f"Fin de carga puesto {i+1}"] = None
            fila[f"Tiempo carga puesto {i+1}"] = None
        # Columnas 21–30
        fila["Estados puestos de validación"] = None
        fila["Cola de validación"] = None
        fila["Tiempo validación"] = None
        fila["Fin de validación"] = None
        fila["Acumulador tiempo USB C"] = None
        fila["Acumulador tiempo Lightning"] = None
        fila["Acumulador tiempo MicroUSB"] = None
        fila["Recaudación USB C"] = None
        fila["Recaudación Lightning"] = None
        fila["Recaudación MicroUSB"] = None
        fila["Recaudacion Total"] = 0.0
        fila["Acumulador Dispositivos Aceptados"] = None
        fila["Acumulador Dispositivos Rechazados"] = None
        

        # ===== Caso 1: Llegada de dispositivo =====
        if evento.tipo == "arrival":
            # 1) RND dispositivo para elegir tipo
            u_device = random.random()
            if u_device < p_usb_c:
                tipo_disp = "USB-C"
            elif u_device < p_usb_c + p_lightning:
                tipo_disp = "Lightning"
            else:
                tipo_disp = "MicroUSB"

            # 2) RND tiempo para el siguiente interarribo
            u_tiempo = random.random()
            interarribo = -media_interarribo * math.log(1 - u_tiempo)
            prox_llegada = clock + interarribo

            # 3) Completar columnas de llegada
            fila["Evento"] = "Llegada dispositivo"
            fila["RND dispositivo"] = round(u_device, 4)
            fila["Tipo dispositivo"] = tipo_disp
            fila["RND tiempo"] = round(u_tiempo, 4)
            fila["Tiempo entre llegadas"] = round(interarribo, 4)
            fila["Próxima llegada"] = round(prox_llegada, 4)

            # 4) Intentar ocupar un servidor libre
            idx_libres = [i for i, srv in enumerate(servidores) if not srv["ocupado"]]
            if idx_libres:
                idx_ser = idx_libres[0]
                servidores[idx_ser]["ocupado"] = True
                servidores[idx_ser]["device_type"] = tipo_disp
                servidores[idx_ser]["etapa"] = "cargando"

                # 5) RND carga y calcular duración
                carga_horas, u_tiempo_carga = seleccionar_tiempo_carga()
                dur_carga_min = carga_horas * 60
                t_fin_carga = clock + dur_carga_min
                servidores[idx_ser]["fin_carga"] = t_fin_carga
                servidores[idx_ser]["duracion_carga"] = dur_carga_min

                # 7) Programar fin de carga
                data_carga = (idx_ser, tipo_disp, t_fin_carga)
                heapq.heappush(eventos_futuros, Evento(t_fin_carga, "end_charge", data_carga))

                # 8) Completar columnas de RND carga y Tiempo carga
                fila["RND carga"] = round(u_tiempo_carga, 4)
                fila["Tiempo carga"] = int(dur_carga_min)

                n_aceptadas += 1
                
            else:
                # Rechazo la llegada
                n_rechazadas += 1

            # 9) Programar siguiente llegada
            heapq.heappush(eventos_futuros, Evento(prox_llegada, "arrival"))

        # ===== Caso 2: Fin de carga =====
        elif evento.tipo == "end_charge":
            idx_ser, tipo_disp, t_fin_carga = evento.data

            fila["Evento"] = "Fin de carga"

            # acumulamos la duracion de la carga y su recaudacion en su tipo
            dur_carga_min = servidores[idx_ser]["duracion_carga"]
            if dur_carga_min is not None:
                if tipo_disp == "USB-C":
                    acum_time_usb_c += dur_carga_min
                    rec_usb_c += tarifas["USB-C"] * (dur_carga_min / 60)
                    recaudacion_total += tarifas["USB-C"] * (dur_carga_min / 60)
                elif tipo_disp == "Lightning":
                    acum_time_lightning += dur_carga_min
                    rec_lightning += tarifas["Lightning"] * (dur_carga_min / 60)
                    recaudacion_total += tarifas["Lightning"] * (dur_carga_min / 60)
                else:  # MicroUSB
                    acum_time_microusb += dur_carga_min
                    rec_microusb += tarifas["MicroUSB"] * (dur_carga_min / 60)
                    recaudacion_total += tarifas["MicroUSB"] * (dur_carga_min / 60)

            
            # 1) El servidor queda libre para cargar, pero el dispositivo va a validación
            servidores[idx_ser]["etapa"] = None
            servidores[idx_ser]["fin_carga"] = None

            servidores[idx_ser]["duracion_carga"] = None

            # 2) Validación centralizada
            if puesto_validacion_libre:
                puesto_validacion_libre = False
                t_fin_valid = clock + tiempo_validacion
                heapq.heappush(eventos_futuros, Evento(t_fin_valid, "end_validation", (idx_ser, tipo_disp, t_fin_valid)))
                fila["Cola de validación"] = len(cola_validacion)
                fila["Fin de validación"] = round(t_fin_valid, 4)
                fila["Tiempo validación"] = tiempo_validacion  # ← Solo aquí
            else:
                cola_validacion.append((idx_ser, tipo_disp))
                fila["Cola de validación"] = len(cola_validacion)
                fila["Fin de validación"] = None
                # No asignar aquí, se pone 0 al final

        # ===== Caso 3: Fin de validación =====
        elif evento.tipo == "end_validation":
            idx_ser, tipo_disp, t_fin_valid = evento.data

            fila["Evento"] = "Fin de validación"

            # 1) Liberar servidor
            servidores[idx_ser]["ocupado"] = False
            servidores[idx_ser]["device_type"] = None
            servidores[idx_ser]["etapa"] = None
            servidores[idx_ser]["fin_validacion"] = None

            # 2) Liberar puesto de validación o pasar al siguiente de la cola
            if cola_validacion:
                next_idx_ser, next_tipo_disp = cola_validacion.pop(0)
                t_fin_valid_next = clock + tiempo_validacion
                heapq.heappush(eventos_futuros, Evento(t_fin_valid_next, "end_validation", (next_idx_ser, next_tipo_disp, t_fin_valid_next)))
                fila["Cola de validación"] = len(cola_validacion)
                fila["Fin de validación"] = round(t_fin_valid_next, 4)
                fila["Tiempo validación"] = tiempo_validacion 
            else:
                puesto_validacion_libre = True
                fila["Cola de validación"] = 0
                fila["Fin de validación"] = None
                # No asignar aquí, se pone 0 al final

        else:
            # No debería pasar
            continue

        # # ===== Columnas 9–10: Cant dispositivos en puerto y % puestos en uso =====
        # ocupados = sum(1 for srv in servidores if srv["ocupado"])
        # fila["Cant dispositivos en puerto"] = ocupados

        # porcentaje_en_uso = (ocupados / n_servidores) * 100 if n_servidores > 0 else 0.0
        # fila["Porcentaje Puestos en uso"] = porcentaje_en_uso
        # acum_porcentaje_puestos += porcentaje_en_uso
        # fila["Acum porcentaje puestos en uso"] = acum_porcentaje_puestos

        # fila["Promedio porcentaje puestos en uso"] = round((acum_porcentaje_puestos / evento_id), 4) if evento_id > 0 else 0.0


        # ===== Columnas 9–10: Cant dispositivos en puerto y % puestos en uso (PONDERADO EN EL TIEMPO CORRECTO) =====
        ## BASICAMENTE LO QUE SE HACE ES VER CUANTO TIEMPO ESTUVO OCUPADO EL SERVIDOR DESDE EL ULTIMO EVENTO Y CON ESO ACUMULAR EL PORCENTAJE PONDERADO Y DIVIDIRLO POR EL TIEMPO TOTAL
        ocupados = sum(1 for srv in servidores if srv["ocupado"])
        fila["Cant dispositivos en puerto"] = ocupados

        # Estado actual (para guardar y mostrar en esta fila)
        porcentaje_en_uso = (ocupados / n_servidores) * 100 if n_servidores > 0 else 0.0
        fila["Porcentaje Puestos en uso"] = porcentaje_en_uso

        # Pero para ponderar, usamos el estado anterior
        porcentaje_previo = (n_ocupados_previo / n_servidores) * 100 if n_servidores > 0 else 0.0
        ponderado_actual = porcentaje_previo * delta_t # Estamos ponderando por la cantidad de tiempo que estuvo ocupado el servidor desde el último evento

        if evento_id == 1:
            acum_porcentaje_ponderado = ponderado_actual
            acum_tiempo_ponderado = delta_t
        else:
            acum_porcentaje_ponderado += ponderado_actual
            acum_tiempo_ponderado += delta_t

        fila["Acum porcentaje puestos en uso (ponderado)"] = round(acum_porcentaje_ponderado, 4)
        fila["Promedio porcentaje puestos en uso (ponderado)"] = round((acum_porcentaje_ponderado / acum_tiempo_ponderado), 4) if acum_tiempo_ponderado > 0 else 0.0 
        ##Si bien estamos usando el acum_tiempo_ponderado, este es igual al tiempo actual de la simulación, pero lo hacemos para poder entender mejor el concepto de ponderación
        
        # Actualizar ocupados previos
        n_ocupados_previo = ocupados

        # ===== Columnas 13–20: Fin de carga puesto 1..8 =====
        for i in range(n_servidores):
            key = f"Fin de carga puesto {i+1}"
            fin_carga_i = servidores[i]["fin_carga"]
            fila[key] = round(fin_carga_i, 4) if fin_carga_i is not None else None

            key2 = f"Tiempo carga puesto {i+1}"
            dur_i = servidores[i]["duracion_carga"]    # lo que aún falta en ese servidor
            fila[key2] = int(dur_i) if dur_i is not None else None

        # ===== Columna 21: Estados puestos de validación =====
        fila["Estados puestos de validación"] = "Libre" if puesto_validacion_libre else "Ocupado"

        # ===== Columna 22: Cola de validación =====
        if "Cola de validación" not in fila or fila["Cola de validación"] is None:
            fila["Cola de validación"] = len(cola_validacion)

        # ===== Columna 23: Tiempo validación =====
        if "Tiempo validación" not in fila or fila["Tiempo validación"] is None:
            fila["Tiempo validación"] = 0  # En el resto de los eventos, 0

        # ===== Columna 24: Fin de validación =====
        # Se colocó en el caso “Fin de carga”; en otros eventos queda None

        # ===== Columnas 25–27: Acumuladores tiempo de carga por tipo =====
        fila["Acumulador tiempo USB C"] = acum_time_usb_c
        fila["Acumulador tiempo Lightning"] = acum_time_lightning
        fila["Acumulador tiempo MicroUSB"] = acum_time_microusb

        # ===== Columnas 28–30: Recaudación por tipo =====
        fila["Recaudación USB C"] = round(rec_usb_c, 2)
        fila["Recaudación Lightning"] = round(rec_lightning, 2)
        fila["Recaudación MicroUSB"] = round(rec_microusb, 2)
        fila["Recaudacion Total"] = recaudacion_total
        fila["Acumulador Dispositivos Aceptados"] = n_aceptadas
        fila["Acumulador Dispositivos Rechazados"] = n_rechazadas
        

        # ===== Agregar fila completa al vector de estado =====
        vector_estado.append(fila)

        

    
    utilizacion_promedio = vector_estado[-1]["Promedio porcentaje puestos en uso"]

    resumen = {
        "n_aceptadas": n_aceptadas,
        "n_rechazadas": n_rechazadas,
        "recaudacion_total": round(recaudacion_total, 2),
        "utilizacion_promedio": round(utilizacion_promedio, 2)
    }

    ultima_fila = vector_estado[-1] if vector_estado else None
    return vector_estado, resumen, ultima_fila


# ===== RUTA PRINCIPAL =====

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        error_msg = None
        try:
            T_max = float(request.form.get("T_max", "0"))
            N_max = int(request.form.get("N_max", "0"))

            media_interarribo = float(request.form.get("media_interarribo", "13"))
            tiempo_validacion = float(request.form.get("tiempo_validacion", "2"))

            p_usb_c = float(request.form.get("p_usb_c", "0.45"))
            p_lightning = float(request.form.get("p_lightning", "0.25"))
            p_microusb = float(request.form.get("p_microusb", "0.30"))

            n_servidores = int(request.form.get("n_servidores", "8"))

            suma_probs = p_usb_c + p_lightning + p_microusb
            if (abs(suma_probs - 1.0) > 1e-6) or (p_usb_c < 0 or p_lightning < 0 or p_microusb < 0):
                error_msg = "Los porcentajes de USB-C, Lightning y MicroUSB deben sumar 1.0. y no pueden ser negativos."
            if (T_max < 0 or N_max < 0 or tiempo_validacion < 0 or media_interarribo < 0):
                error_msg = "Los valores  del tiempo de simulación, tiempo de validación, cantidad de iteraciones o cantidad media de llegada no pueden sser negativos "

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
            tiempo_validacion=tiempo_validacion,
            n_servidores=n_servidores 
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

    # GET → mostrar formulario con valores por defecto
    return render_template("index.html",
                           error=None,
                           resumen=None,
                           ultima_fila=None,
                           vector_estado=None)


if __name__ == "__main__":
    app.run(debug=True)
