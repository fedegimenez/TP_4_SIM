#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py

Aplicación Flask que implementa la simulación de “Puestos de Carga – Festival Río Vivo”
(punto B del TP4), con un vector de estado de 30 columnas en cada iteración.

Columnas del vector de estado (por fila):
  1. Iteraciones                        - Número secuencial del evento (1, 2, 3, …)
  2. Reloj                              - Tiempo simulación en minutos (float)
  3. Evento                             - Tipo de evento: "INICIO SIM", "Llegada dispositivo", "Fin de carga", "Fin de validación"
  4. RND dispositivo                    - Número aleatorio usado para elegir tipo de dispositivo
  5. Tipo dispositivo                   - Tipo seleccionado: "USB-C", "Lightning", "MicroUSB"
  6. RND tiempo                         - Número aleatorio usado para calcular siguiente interarribo
  7. Tiempo entre llegadas              - Duración del interarribo en minutos (float)
  8. Próxima llegada                    - Tiempo futuro de la siguiente llegada (minutos)
  9. Cant dispositivos en puerto        - Cantidad de servidores actualmente ocupados
 10. Porcentaje Puestos en uso          - (ocupados / n_servidores) * 100
 11. Acum porcentaje puestos en uso (ponderado) - Acumulado del área bajo la curva de ocupación
 12. Promedio porcentaje puestos en uso (ponderado) - Acum porcentaje puestos en uso (ponderado) / tiempo total transcurrido
 13. RND carga                          - Número aleatorio usado para determinar duración de carga
 14. Tiempo carga                       - Duración de la carga en minutos (int)

 15. Fin de carga puesto 1              - Tiempo en que el servidor 1 terminará su carga (float o None)
 16. Tiempo carga puesto 1              - Duración pendiente de carga en el servidor 1 (int o None)
 17. Fin de carga puesto 2              - Tiempo en que el servidor 2 terminará su carga
 18. Tiempo carga puesto 2              - Duración pendiente de carga en el servidor 2 (int o None)
 19. Fin de carga puesto 3              - Tiempo en que el servidor 3 terminará su carga
 20. Tiempo carga puesto 3              - Duración pendiente de carga en el servidor 3 (int o None)
 21. Fin de carga puesto 4              - Tiempo en que el servidor 4 terminará su carga
 22. Tiempo carga puesto 4              - Duración pendiente de carga en el servidor 4 (int o None)
 23. Fin de carga puesto 5              - Tiempo en que el servidor 5 terminará su carga
 24. Tiempo carga puesto 5              - Duración pendiente de carga en el servidor 5 (int o None)
 25. Fin de carga puesto 6              - Tiempo en que el servidor 6 terminará su carga
 26. Tiempo carga puesto 6              - Duración pendiente de carga en el servidor 6 (int o None)
 27. Fin de carga puesto 7              - Tiempo en que el servidor 7 terminará su carga
 28. Tiempo carga puesto 7              - Duración pendiente de carga en el servidor 7 (int o None)
 29. Fin de carga puesto 8              - Tiempo en que el servidor 8 terminará su carga
 30. Tiempo carga puesto 8              - Duración pendiente de carga en el servidor 8 (int o None)
 
 31. Estados puestos de validación      - "Libre" o "Ocupado" según si el puesto de validación está libre
 32. Cola de validación                 - Cantidad de dispositivos en cola de validación
 33. Tiempo validación                  - Duración fija del proceso de validación (minutos)
 34. Fin de validación                  - Tiempo en que terminará la validación del dispositivo en curso
 35. Acumulador tiempo USB C            - Suma total (en minutos) de todas las cargas USB-C hasta ese instante
 36. Acumulador tiempo Lightning        - Suma total (en minutos) de todas las cargas Lightning hasta ese instante
 37. Acumulador tiempo MicroUSB         - Suma total (en minutos) de todas las cargas MicroUSB hasta ese instante
 38. Recaudación USB C                  - Ingresos acumulados (en $) por cargas USB-C hasta ese instante
 39. Recaudación Lightning              - Ingresos acumulados (en $) por cargas Lightning hasta ese instante
 40. Recaudación MicroUSB               - Ingresos acumulados (en $) por cargas MicroUSB hasta ese instante
 41. Recaudacion Total                  - Suma de recaudaciones por todos los tipos de carga
 42. Acumulador Dispositivos Aceptados  - Contador de cuántos dispositivos fueron atendidos (no rechazados)
 43. Acumulador Dispositivos Rechazados - Contador de cuántos dispositivos fueron rechazados (sin servidor libre)

Para ejecutar:
  1. Instalar Flask (si no lo tienes):  `pip install flask`
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
    Representa un evento en la simulación de tipo:
      - "arrival": llegada de un dispositivo
      - "end_charge": fin de carga de un dispositivo en un servidor
      - "end_validation": fin de validación de un dispositivo
    Atributos:
      - tiempo: instante en minutos (float) en que ocurre el evento
      - tipo: str indicando el tipo de evento
      - data: datos extra para el evento:
          * Para "arrival": None
          * Para "end_charge": (idx_servidor, tipo_dispositivo, tiempo_fin_carga)
          * Para "end_validation": (idx_servidor, tipo_dispositivo, tiempo_fin_validación)
    Internamente:
      - _orden: contador secuencial que permite desempatar eventos con mismo tiempo
    """
    _contador_global = 0

    def __init__(self, tiempo, tipo, data=None):
        self.tiempo = tiempo
        self.tipo = tipo
        self.data = data
        # Asigna un orden incremental para romper empates en el heap
        self._orden = Evento._contador_global
        Evento._contador_global += 1

    def __lt__(self, otro):
        # Ordena primero por tiempo; si hay empate, por orden de creación (_orden)
        if self.tiempo == otro.tiempo:
            return self._orden < otro._orden
        return self.tiempo < otro.tiempo


def generar_interarribo(media):
    """
    Genera un tiempo de interarribo ~ Exponencial con media dada (en minutos).
    Se usa el método inverso: -media * ln(1 - u).
    Devuelve un float que es la duración en minutos hasta la próxima llegada.
    """
    u = random.random()
    return -media * math.log(1 - u)


def seleccionar_tiempo_carga():
    """
    Selección del tiempo de carga de forma discreta:
      - Horas de carga posibles: 1, 2, 3, 4
      - Probabilidades: P(1h)=0.50, P(2h)=0.30, P(3h)=0.15, P(4h)=0.05
    Retorna:
      - carga_horas: entero cantidad de horas (1,2,3 o 4)
      - u_tiempo: número aleatorio usado para la selección (para registrar RND carga)
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
    Ejecuta la simulación.

    Parámetros:
      - T_max: tiempo máximo de simulación (en minutos). Si el reloj excede T_max, se detiene.
      - N_max: número máximo de eventos a procesar antes de detener la simulación.
      - media_interarribo: media (minutos) para la distribución exponencial de llegadas.
      - p_usb_c: probabilidad de llegada de dispositivo USB-C.
      - p_lightning: probabilidad de llegada de dispositivo Lightning.
      - p_microusb: probabilidad de llegada de dispositivo MicroUSB.
      - tiempo_validacion: tiempo fijo (minutos) que tarda la validación de cada dispositivo.
      - n_servidores: cantidad de puestos de carga disponibles (servidores).

    Retorna:
      - vector_estado: lista de diccionarios, cada uno representando una fila con las 43 columnas descritas.
      - resumen: diccionario con:
          * n_aceptadas: cantidad de dispositivos atendidos (no rechazados)
          * n_rechazadas: cantidad de dispositivos rechazados
          * recaudacion_total: ingresos totales generados por todas las cargas
          * utilizacion_promedio: porcentaje promedio de utilización de puestos (ponderado en el tiempo)
      - ultima_fila: diccionario con los mismos campos de la última fila generada en vector_estado
    """

    random.seed()  # Inicializa semilla aleatoria (Podemos setear una semilla específica si se desea reproducibilidad)

    # ===== Parámetros fijos de tarifas ($ por hora de carga) =====
    tarifas = {"USB-C": 300, "Lightning": 500, "MicroUSB": 1000}
    # El puesto de validación se modela como un recurso único (True=libre, False=ocupado)
    puesto_validacion_libre = True
    # Cola FIFO de dispositivos esperando validación: cada elemento = (idx_servidor, tipo_dispositivo)
    cola_validacion = []

    # ===== Estado de cada servidor de carga =====
    # Cada servidor es un diccionario con:
    #   "ocupado": bool -> True si hay un dispositivo cargando, False si libre
    #   "device_type": str -> tipo de dispositivo que está cargando ("USB-C", "Lightning", "MicroUSB")
    #   "etapa": str -> "cargando" o "validando" (o None si no hay nada)
    #   "fin_carga": float o None -> instante en que terminará la carga en minutos
    #   "fin_validacion": float o None -> instante en que terminará la validación en minutos
    #   "duracion_carga": float o None -> duración de la carga en minutos para este dispositivo
    servidores = [
        {"ocupado": False, "device_type": None, "etapa": None,
         "fin_carga": None, "fin_validacion": None, "duracion_carga": None}
        for _ in range(n_servidores)
    ]

    # ===== Cola de eventos futuros (priority queue ordenada por tiempo) =====
    eventos_futuros = []

    # ===== Crear fila 0: Estado inicial ("INICIO SIM") =====
    # Generar RND tiempo inicial para la primera llegada:
    u_tiempo0 = random.random()
    interarribo0 = -media_interarribo * math.log(1 - u_tiempo0)
    prox_llegada0 = interarribo0  # tiempo de la primera llegada

    # Fila 0: todos los campos inicializados
    fila0 = {
        "Iteraciones": 0,
        "Reloj": 0.0,                         # En inicio, reloj=0
        "Evento": "Inicio Simulacion",              # Tipo de evento
        "RND dispositivo": None,             # No se genera dispositivo en inicio
        "Tipo dispositivo": None,            # No aplica
        "RND tiempo": round(u_tiempo0, 4),   # RND usado para primer interarribo
        "Tiempo entre llegadas": round(interarribo0, 4),
        "Próxima llegada": round(prox_llegada0, 4),
        "Cant dispositivos en puerto": 0,    # Ningún servidor ocupado al inicio
        "Porcentaje Puestos en uso": 0.0,    # 0% al inicio
        "Acum porcentaje puestos en uso": 0.0,  # Acumulado inicial
        "Promedio porcentaje puestos en uso": 0.0,  # Promedio inicial
        "RND carga": None,                   # No hay carga en inicio
        "Tiempo carga": None,                # No hay carga en inicio
    }
    # Columnas 15–30: para cada servidor, inicializa "Fin de carga" y "Tiempo carga" en None
    for i in range(n_servidores):
        fila0[f"Fin de carga puesto {i+1}"] = None
        fila0[f"Tiempo carga puesto {i+1}"] = None

    # Columnas 31–34: validación, acumuladores y recaudaciones inicializadas
    fila0["Estados puestos de validación"] = "Libre"   # No hay nadie validando al inicio
    fila0["Cola de validación"] = 0                    # Cola vacía
    fila0["Tiempo validación"] = 0                      # No hay proceso en curso
    fila0["Fin de validación"] = None                   # No aplica

    # Inicializar acumuladores de tiempo de carga en 0
    fila0["Acumulador tiempo USB C"] = 0
    fila0["Acumulador tiempo Lightning"] = 0
    fila0["Acumulador tiempo MicroUSB"] = 0

    # Inicializar recaudaciones en 0
    fila0["Recaudación USB C"] = 0.0
    fila0["Recaudación Lightning"] = 0.0
    fila0["Recaudación MicroUSB"] = 0.0

    # Ingresos totales y contadores de aceptadas/rechazadas en fila 0
    fila0["Recaudacion Total"] = 0.0
    fila0["Acumulador Dispositivos Aceptados"] = 0
    fila0["Acumulador Dispositivos Rechazados"] = 0

    # Inicia el vector de estado con la fila 0
    vector_estado = [fila0]

    # ===== Programar la primera llegada al heap de eventos =====
    heapq.heappush(eventos_futuros, Evento(prox_llegada0, "arrival"))

    # ===== Variables acumuladas a lo largo de la simulación =====
    clock = 0.0                    # Reloj actual de simulación
    evento_id = 0                  # Contador de iteraciones (filas generadas)
    n_aceptadas = 0                # Contador de dispositivos aceptados
    n_rechazadas = 0               # Contador de dispositivos rechazados
    recaudacion_total = 0.0        # Ingresos totales acumulados

    # Variables para el cálculo de uso ponderado
    reloj_previo = 0.0             # Último instante registrado
    n_ocupados_previo = 0          # Puestos ocupados en el instante anterior

    acum_porcentaje_ponderado = 0.0  # Para calcular porcentaje de uso ponderado
    acum_tiempo_ponderado = 0.0       # Tiempo total transcurrido (para ponderar)

    # Acumuladores de tiempo de carga por tipo de dispositivo
    acum_time_usb_c = 0
    acum_time_lightning = 0
    acum_time_microusb = 0

    # Acumuladores de recaudación por tipo de dispositivo
    rec_usb_c = 0.0
    rec_lightning = 0.0
    rec_microusb = 0.0

    # ===== Bucle principal de eventos (hasta N_max eventos o hasta agotar heap) =====
    while eventos_futuros and evento_id < N_max:
        # Obtener el evento con menor tiempo del heap
        evento = heapq.heappop(eventos_futuros)
        t_evt = evento.tiempo

        # Si el siguiente evento ocurre después de T_max, terminamos la simulación
        if t_evt > T_max:
            break

        # Avanzamos el reloj de simulación
        clock = t_evt

        # Calcular el tiempo transcurrido desde el último evento y setear el proximo reloj previo para la iteración que viene
        delta_t = clock - reloj_previo
        reloj_previo = clock

        # Incrementar contador de iteración (firma de la nueva fila a crear)
        evento_id += 1

        # ===== Crear una nueva fila base con todas las columnas inicializadas a None o 0 =====
        fila = {
            "Iteraciones": evento_id,
            "Reloj": round(clock, 4),
            "Evento": None,               # Se asignará según tipo de evento
            "RND dispositivo": None,      # RND para tipo de dispositivo (en llegada)
            "Tipo dispositivo": None,     # Tipo elegido (en llegada)
            "RND tiempo": None,           # RND para interarribo (en llegada)
            "Tiempo entre llegadas": None,
            "Próxima llegada": None,
            "Cant dispositivos en puerto": None,
            "Porcentaje Puestos en uso": None,
            "Acum porcentaje puestos en uso (ponderado)": None,
            "Promedio porcentaje puestos en uso (ponderado)": None,
            "RND carga": None,            # RND para tiempo de carga (en asignación)
            "Tiempo carga": None,         # Duración de la carga (en asignación)
        }
        # Columnas para cada servidor: Fin de carga y Tiempo carga
        for i in range(n_servidores):
            fila[f"Fin de carga puesto {i+1}"] = None
            fila[f"Tiempo carga puesto {i+1}"] = None

        # Columnas de validación y de acumuladores
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

        # ===== Caso 1: Evento de llegada ("arrival") =====
        if evento.tipo == "arrival":
            # 1) Generar RND para escoger tipo de dispositivo segun probabilidades
            u_device = random.random()
            if u_device < p_usb_c:
                tipo_disp = "USB-C"
            elif u_device < p_usb_c + p_lightning:
                tipo_disp = "Lightning"
            else:
                tipo_disp = "MicroUSB"

            # 2) Generar RND tiempo para calcular próximo interarribo (exponencial)
            u_tiempo = random.random()
            interarribo = -media_interarribo * math.log(1 - u_tiempo)
            prox_llegada = clock + interarribo

            # 3) Llenar columnas relacionadas con la llegada
            fila["Evento"] = "Llegada dispositivo"
            fila["RND dispositivo"] = round(u_device, 4)
            fila["Tipo dispositivo"] = tipo_disp
            fila["RND tiempo"] = round(u_tiempo, 4)
            fila["Tiempo entre llegadas"] = round(interarribo, 4)
            fila["Próxima llegada"] = round(prox_llegada, 4)

            # 4) Intentar asignar un servidor de carga libre
            idx_libres = [i for i, srv in enumerate(servidores) if not srv["ocupado"]]
            if idx_libres:
                # Si hay al menos un servidor libre, tomar el primero
                idx_ser = idx_libres[0]
                servidores[idx_ser]["ocupado"] = True
                servidores[idx_ser]["device_type"] = tipo_disp
                servidores[idx_ser]["etapa"] = "cargando"

                # 5) Generar RND carga y calcular duración de la carga en minutos
                carga_horas, u_tiempo_carga = seleccionar_tiempo_carga()
                dur_carga_min = carga_horas * 60
                t_fin_carga = clock + dur_carga_min
                servidores[idx_ser]["fin_carga"] = t_fin_carga
                servidores[idx_ser]["duracion_carga"] = dur_carga_min

                # 6) Programar evento de fin de carga para este servidor
                data_carga = (idx_ser, tipo_disp, t_fin_carga)
                heapq.heappush(eventos_futuros, Evento(t_fin_carga, "end_charge", data_carga))

                # 7) Llenar columnas de RND carga y Tiempo carga
                fila["RND carga"] = round(u_tiempo_carga, 4)
                fila["Tiempo carga"] = int(dur_carga_min)

                # 8) Incrementar contador de aceptadas
                n_aceptadas += 1
            else:
                # No hay servidor libre -> rechazar dispositivo
                n_rechazadas += 1

            # 9) Programar la siguiente llegada (aunque se haya rechazado o atendido)
            heapq.heappush(eventos_futuros, Evento(prox_llegada, "arrival"))

        # ===== Caso 2: Fin de carga ("end_charge") =====
        elif evento.tipo == "end_charge":
            idx_ser, tipo_disp, t_fin_carga = evento.data

            fila["Evento"] = "Fin de carga"

            # Acumular tiempo de carga y recaudación según tipo de dispositivo
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
                else:  # "MicroUSB"
                    acum_time_microusb += dur_carga_min
                    rec_microusb += tarifas["MicroUSB"] * (dur_carga_min / 60)
                    recaudacion_total += tarifas["MicroUSB"] * (dur_carga_min / 60)

            # 1) Liberar la etapa de carga del servidor (pues ahora va a validación)
            servidores[idx_ser]["etapa"] = None
            servidores[idx_ser]["fin_carga"] = None
            servidores[idx_ser]["duracion_carga"] = None

            # 2) Enviar dispositivo a validación centralizada
            if puesto_validacion_libre:
                # Si el puesto de validación está libre, asignar inmediatamente
                puesto_validacion_libre = False
                t_fin_valid = clock + tiempo_validacion
                heapq.heappush(eventos_futuros, Evento(t_fin_valid, "end_validation", (idx_ser, tipo_disp, t_fin_valid)))
                fila["Cola de validación"] = len(cola_validacion)
                fila["Fin de validación"] = round(t_fin_valid, 4)
                fila["Tiempo validación"] = tiempo_validacion
            else:
                # Si el puesto está ocupado, encolar el servidor y tipo
                cola_validacion.append((idx_ser, tipo_disp))
                fila["Cola de validación"] = len(cola_validacion)
                fila["Fin de validación"] = None
                fila["Tiempo validación"] = 0  # No está en validación en este instante

        # ===== Caso 3: Fin de validación ("end_validation") =====
        elif evento.tipo == "end_validation":
            idx_ser, tipo_disp, t_fin_valid = evento.data

            fila["Evento"] = "Fin de validación"

            # 1) Liberar el servidor de carga (ya finalizó todo proceso)
            servidores[idx_ser]["ocupado"] = False
            servidores[idx_ser]["device_type"] = None
            servidores[idx_ser]["etapa"] = None
            servidores[idx_ser]["fin_validacion"] = None

            # 2) Si hay más dispositivos en cola de validación, asignar el siguiente
            if cola_validacion:
                next_idx_ser, next_tipo_disp = cola_validacion.pop(0)
                t_fin_valid_next = clock + tiempo_validacion
                heapq.heappush(eventos_futuros, Evento(t_fin_valid_next, "end_validation", (next_idx_ser, next_tipo_disp, t_fin_valid_next)))
                fila["Cola de validación"] = len(cola_validacion)
                fila["Fin de validación"] = round(t_fin_valid_next, 4)
                fila["Tiempo validación"] = tiempo_validacion
            else:
                # No hay más en cola -> puesto de validación queda libre
                puesto_validacion_libre = True
                fila["Cola de validación"] = 0
                fila["Fin de validación"] = None
                fila["Tiempo validación"] = 0

        else:
            # No debería ocurrir otro tipo de evento
            continue

        # ===== Columnas 9–10-11: Cant. de dispositivos en puerto y % de uso de puestos =====
        ocupados = sum(1 for srv in servidores if srv["ocupado"])
        fila["Cant dispositivos en puerto"] = ocupados

        # Cálculo del porcentaje de uso actual
        porcentaje_en_uso = (ocupados / n_servidores) * 100 if n_servidores > 0 else 0.0
        fila["Porcentaje Puestos en uso"] = round(porcentaje_en_uso, 4)

        # ===== Cálculo de uso PONDERADO en el tiempo =====
        # Usamos el número de ocupados del instante anterior (n_ocupados_previo)
        porcentaje_previo = (n_ocupados_previo / n_servidores) * 100 if n_servidores > 0 else 0.0

        ponderado_actual = porcentaje_previo * delta_t

        if evento_id == 1:
            # En la primera iteración, acumulamos directamente
            acum_porcentaje_ponderado = ponderado_actual
            acum_tiempo_ponderado = delta_t
        else:
            acum_porcentaje_ponderado += ponderado_actual
            acum_tiempo_ponderado += delta_t

        fila["Acum porcentaje puestos en uso (ponderado)"] = round(acum_porcentaje_ponderado, 4)
        # Promedio ponderado = área acumulada / tiempo total transcurrido
        fila["Promedio porcentaje puestos en uso (ponderado)"] = round(
            (acum_porcentaje_ponderado / acum_tiempo_ponderado), 4
        ) if acum_tiempo_ponderado > 0 else 0.0

        # Actualizar estado previo para la próxima iteración
        n_ocupados_previo = ocupados

        # ===== Columnas 15–30: Fin de carga y Tiempo carga por servidor =====
        for i in range(n_servidores):
            # Tiempo exacto en que terminará la carga en el servidor i (o None si libre)
            fin_carga_i = servidores[i]["fin_carga"]
            fila[f"Fin de carga puesto {i+1}"] = round(fin_carga_i, 4) if fin_carga_i is not None else None

            # Duración pendiente de carga para ese servidor (en minutos) o None
            dur_i = servidores[i]["duracion_carga"]
            fila[f"Tiempo carga puesto {i+1}"] = int(dur_i) if dur_i is not None else None

        # ===== Columna 31: Estados puestos de validación =====
        fila["Estados puestos de validación"] = "Libre" if puesto_validacion_libre else "Ocupado"

        # ===== Columna 32: Cola de validación =====
        # Si ya fue llenado en el caso específico, mantenemos ese valor; si no, lo calculamos
        if fila["Cola de validación"] is None:
            fila["Cola de validación"] = len(cola_validacion)

        # ===== Columna 33: Tiempo validación =====
        # Si ya fue llenado (en fin de carga o fin de validación), mantenerlo; sino es 0
        if fila["Tiempo validación"] is None:
            fila["Tiempo validación"] = 0

        # ===== Columna 34: Fin de validación =====
        # Solo se asigna cuando se programa un fin de validación. Si no, queda None.

        # ===== Columnas 35-37: Acumuladores de tiempo de carga por tipo =====
        fila["Acumulador tiempo USB C"] = acum_time_usb_c
        fila["Acumulador tiempo Lightning"] = acum_time_lightning
        fila["Acumulador tiempo MicroUSB"] = acum_time_microusb

        # ===== Columnas 38-41: Recaudación por tipo y total =====
        fila["Recaudación USB C"] = round(rec_usb_c, 2)
        fila["Recaudación Lightning"] = round(rec_lightning, 2)
        fila["Recaudación MicroUSB"] = round(rec_microusb, 2)
        fila["Recaudacion Total"] = round(recaudacion_total, 2)

        # ===== Columnas 42-43: Acumuladores de aceptadas y rechazadas =====
        fila["Acumulador Dispositivos Aceptados"] = n_aceptadas
        fila["Acumulador Dispositivos Rechazados"] = n_rechazadas

        # ===== Agregar la fila completa al vector de estado =====
        vector_estado.append(fila)

    # ===== Cálculo final fuera del bucle =====
    # La utilización promedio global es la de la última fila
    utilizacion_promedio = vector_estado[-1]["Promedio porcentaje puestos en uso (ponderado)"]

    resumen = {
        "n_aceptadas": n_aceptadas,
        "n_rechazadas": n_rechazadas,
        "recaudacion_total": round(recaudacion_total, 2),
        "utilizacion_promedio": round(utilizacion_promedio, 2)
    }

    ultima_fila = vector_estado[-1] if vector_estado else None
    return vector_estado, resumen, ultima_fila


# ===== RUTA PRINCIPAL de la aplicación Flask =====
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        error_msg = None
        try:
            # Extraer valores del formulario y convertir a tipos adecuados
            T_max = float(request.form.get("T_max", "0"))
            N_max = int(request.form.get("N_max", "0"))
            media_interarribo = float(request.form.get("media_interarribo", "13"))
            tiempo_validacion = float(request.form.get("tiempo_validacion", "2"))
            p_usb_c = float(request.form.get("p_usb_c", "0.45"))
            p_lightning = float(request.form.get("p_lightning", "0.25"))
            p_microusb = float(request.form.get("p_microusb", "0.30"))
            n_servidores = int(request.form.get("n_servidores", "8"))

            # Validar que las probabilidades sumen 1 y que no haya valores negativos
            suma_probs = p_usb_c + p_lightning + p_microusb
            if (abs(suma_probs - 1.0) > 1e-6) or (p_usb_c < 0 or p_lightning < 0 or p_microusb < 0):
                error_msg = "Los porcentajes de USB-C, Lightning y MicroUSB deben sumar 1.0 y no pueden ser negativos."
            if (T_max < 0 or N_max < 0 or tiempo_validacion < 0 or media_interarribo < 0):
                error_msg = "Los valores numéricos no pueden ser negativos."

        except ValueError:
            error_msg = "Por favor, ingrese valores numéricos válidos en todos los campos."

        if error_msg:
            # Si hay error en validación, renderear la plantilla con mensaje de error
            return render_template(
                "index.html",
                error=error_msg,
                resumen=None,
                ultima_fila=None,
                vector_estado=None
            )

        # ===== Ejecutar la simulación si no hay errores =====
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

        # Si no se generaron filas, informar al usuario
        if not vector:
            return render_template(
                "index.html",
                error="La simulación no produjo ningún evento (revisa los parámetros).",
                resumen=None,
                ultima_fila=None,
                vector_estado=None
            )

        # Renderizar la vista con los resultados de simulación
        return render_template(
            "index.html",
            error=None,
            resumen=resumen,
            ultima_fila=ultima_fila,
            vector_estado=vector
        )

    # GET: mostrar formulario en blanco o con valores por defecto
    return render_template("index.html",
                           error=None,
                           resumen=None,
                           ultima_fila=None,
                           vector_estado=None)


if __name__ == "__main__":
    # Iniciar servidor Flask en modo debug
    app.run(debug=True)
