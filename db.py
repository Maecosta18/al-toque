import sqlite3
from datetime import datetime, time as dtime

from flask import g

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    rol TEXT NOT NULL CHECK (rol IN ('cliente', 'comercio', 'repartidor', 'admin')),
    telefono TEXT,
    activo INTEGER NOT NULL DEFAULT 1,
    creado_en TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS comercios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    nombre TEXT NOT NULL,
    categoria TEXT,
    direccion TEXT,
    lat REAL,
    lng REAL,
    activo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS productos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comercio_id INTEGER NOT NULL REFERENCES comercios(id),
    nombre TEXT NOT NULL,
    descripcion TEXT,
    precio REAL NOT NULL,
    disponible INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS repartidores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    vehiculo TEXT,
    disponible INTEGER NOT NULL DEFAULT 1,
    ultima_lat REAL,
    ultima_lng REAL,
    ubicacion_en TEXT
);

CREATE TABLE IF NOT EXISTS pedidos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL REFERENCES usuarios(id),
    comercio_id INTEGER NOT NULL REFERENCES comercios(id),
    repartidor_id INTEGER REFERENCES repartidores(id),
    estado TEXT NOT NULL DEFAULT 'pendiente_pago',
    direccion_entrega TEXT NOT NULL,
    subtotal REAL NOT NULL,
    costo_envio REAL NOT NULL,
    comision_plataforma REAL NOT NULL,
    monto_comercio REAL NOT NULL,
    total REAL NOT NULL,
    motivo_cancelacion TEXT,
    reintegro_cliente REAL NOT NULL DEFAULT 0,
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS items_pedido (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id INTEGER NOT NULL REFERENCES pedidos(id),
    producto_id INTEGER NOT NULL REFERENCES productos(id),
    nombre_producto TEXT NOT NULL,
    cantidad INTEGER NOT NULL,
    precio_unitario REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS ubicaciones_pedido (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id INTEGER NOT NULL REFERENCES pedidos(id),
    repartidor_id INTEGER NOT NULL REFERENCES repartidores(id),
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    creado_en TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ubicaciones_pedido ON ubicaciones_pedido(pedido_id);

CREATE TABLE IF NOT EXISTS configuracion (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    comision_pct REAL NOT NULL,
    costo_envio_default REAL NOT NULL,
    zona_cobertura TEXT NOT NULL,
    horario_semana_inicio TEXT NOT NULL,
    horario_semana_fin TEXT NOT NULL,
    recargo_cancelacion_pct REAL NOT NULL DEFAULT 0.10,
    servicio_activo INTEGER NOT NULL DEFAULT 1,
    mensaje_mantenimiento TEXT NOT NULL DEFAULT 'Al Toque está fuera de servicio por mantenimiento. Volvemos enseguida.'
);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(config.DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


_MIGRACIONES = [
    "ALTER TABLE comercios ADD COLUMN lat REAL",
    "ALTER TABLE comercios ADD COLUMN lng REAL",
    "ALTER TABLE configuracion ADD COLUMN recargo_cancelacion_pct REAL NOT NULL DEFAULT 0.10",
]


def init_db():
    conn = sqlite3.connect(config.DB_PATH)
    conn.executescript(SCHEMA)
    for sentencia in _MIGRACIONES:
        try:
            conn.execute(sentencia)
        except sqlite3.OperationalError:
            pass  # la columna ya existe (base de datos creada con una versión más nueva)
    existe = conn.execute("SELECT 1 FROM configuracion WHERE id = 1").fetchone()
    if not existe:
        inicio = "%02d:%02d" % config.HORARIO_SEMANA_INICIO
        fin = "%02d:%02d" % config.HORARIO_SEMANA_FIN
        conn.execute(
            "INSERT INTO configuracion (id, comision_pct, costo_envio_default, "
            "zona_cobertura, horario_semana_inicio, horario_semana_fin, servicio_activo) "
            "VALUES (1, ?, ?, ?, ?, ?, 1)",
            (config.COMISION_PLATAFORMA_PCT, config.COSTO_ENVIO_DEFAULT,
             config.ZONA_COBERTURA, inicio, fin),
        )
    conn.commit()
    conn.close()


def get_config():
    """Devuelve la fila de configuración de la plataforma (siempre existe)."""
    conn = get_db()
    return conn.execute("SELECT * FROM configuracion WHERE id = 1").fetchone()


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def haversine_km(lat1, lng1, lat2, lng2):
    """Distancia en línea recta entre dos puntos, en km."""
    import math
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _parse_hhmm(valor: str) -> dtime:
    h, m = valor.split(":")
    return dtime(int(h), int(m))


def dentro_de_horario(cfg=None, momento: "datetime | None" = None) -> bool:
    """Chequea si `momento` (o ahora) cae dentro del horario de operación."""
    momento = momento or datetime.now()
    if momento.weekday() in config.DIAS_24HS:
        return True

    if cfg is None:
        cfg = get_config()

    inicio = _parse_hhmm(cfg["horario_semana_inicio"])
    fin = _parse_hhmm(cfg["horario_semana_fin"])
    hora_actual = momento.time()

    # El horario cruza medianoche (08:00 -> 01:00 del día siguiente)
    if inicio <= fin:
        return inicio <= hora_actual <= fin
    return hora_actual >= inicio or hora_actual <= fin
