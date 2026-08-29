"""
Configuración central de Al Toque.

Estos valores se usan solo para crear la fila inicial de la tabla
`configuracion` la primera vez que se arranca la app. Una vez creada,
el admin edita todo desde /admin/configuracion (panel web) y esos
valores de acá dejan de tener efecto — quedan como referencia de los
defaults originales.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "al_toque.db")

SECRET_KEY = os.environ.get("AL_TOQUE_SECRET_KEY", "cambiar-esta-clave-en-produccion")

# Render define automaticamente la variable de entorno RENDER en todos los
# servicios que corren ahi -- la usamos para saber si estamos en produccion
# (hosting real, siempre con HTTPS) o corriendo local con python app.py.
EN_PRODUCCION = bool(os.environ.get("RENDER"))

# --- Horario de operación (según lo definido para el piloto) ---
# Entre semana: 08:00 a 01:00 (cruza medianoche)
# Sábados y domingos: 24 horas
HORARIO_SEMANA_INICIO = (8, 0)
HORARIO_SEMANA_FIN = (1, 0)  # del día siguiente
DIAS_24HS = {5, 6}  # 0=lunes ... 5=sábado, 6=domingo (weekday() de Python)

# --- Zona de cobertura (descriptiva por ahora, sin geolocalización) ---
ZONA_COBERTURA = "Desde el acceso a Río Segundo hasta el límite entre Pilar y Manfredi"

# --- Comisión de la plataforma ---
# AJUSTAR: % que se descuenta al comercio sobre el subtotal de productos.
COMISION_PLATAFORMA_PCT = 0.15

# AJUSTAR: costo de envío por defecto (va 100% al repartidor).
COSTO_ENVIO_DEFAULT = 800.0

ROLES = ["cliente", "comercio", "repartidor", "admin"]

ESTADOS_PEDIDO = [
    "pendiente_pago",
    "pagado",
    "en_preparacion",
    "listo_para_retirar",
    "en_camino",
    "entregado",
    "cancelado",
]
