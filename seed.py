"""
Datos de ejemplo para poder probar el flujo completo: un comercio con
productos, un repartidor, un cliente y un admin.

Uso local (borra todo y arranca de cero):
    python3 seed.py

`seed_demo_si_vacio()` es la versión segura para llamar automáticamente
al arrancar el servidor (por ejemplo en un hosting con disco que se
reinicia): solo carga los datos de ejemplo si la base está vacía, nunca
borra nada.
"""
from werkzeug.security import generate_password_hash

import config
import db


def seed_demo_si_vacio():
    conn = db.get_db()
    ya_hay_datos = conn.execute("SELECT 1 FROM comercios LIMIT 1").fetchone()
    if ya_hay_datos:
        return
    _insertar_datos_demo(conn)
    conn.commit()


def _insertar_datos_demo(conn):
    now = db.now_iso()

    # --- Comercio piloto ---
    cur = conn.execute(
        "INSERT INTO usuarios (nombre, email, password_hash, rol, telefono, creado_en) "
        "VALUES (?, ?, ?, 'comercio', ?, ?)",
        ("Almacén Don José", "comercio@demo.com", generate_password_hash("demo1234"),
         "3572000000", now),
    )
    comercio_user_id = cur.lastrowid
    cur = conn.execute(
        "INSERT INTO comercios (usuario_id, nombre, categoria, direccion, lat, lng) VALUES (?, ?, ?, ?, ?, ?)",
        (comercio_user_id, "Almacén Don José", "Almacén", "Av. San Martín 123, Río Segundo",
         -31.6512, -63.8908),
    )
    comercio_id = cur.lastrowid

    productos = [
        ("Pan casero (kg)", "Recién horneado", 1800.0),
        ("Docena de huevos", "", 3200.0),
        ("Fernet Branca 750ml", "", 12500.0),
        ("Coca-Cola 1.5L", "", 2600.0),
    ]
    for nombre, desc, precio in productos:
        conn.execute(
            "INSERT INTO productos (comercio_id, nombre, descripcion, precio) VALUES (?, ?, ?, ?)",
            (comercio_id, nombre, desc, precio),
        )

    # --- Repartidor piloto ---
    cur = conn.execute(
        "INSERT INTO usuarios (nombre, email, password_hash, rol, telefono, creado_en) "
        "VALUES (?, ?, ?, 'repartidor', ?, ?)",
        ("Nico Repartidor", "repartidor@demo.com", generate_password_hash("demo1234"),
         "3572000001", now),
    )
    repartidor_user_id = cur.lastrowid
    conn.execute(
        "INSERT INTO repartidores (usuario_id, vehiculo) VALUES (?, ?)",
        (repartidor_user_id, "Moto"),
    )

    # --- Cliente de prueba ---
    conn.execute(
        "INSERT INTO usuarios (nombre, email, password_hash, rol, telefono, creado_en) "
        "VALUES (?, ?, ?, 'cliente', ?, ?)",
        ("Marce Cliente", "cliente@demo.com", generate_password_hash("demo1234"),
         "3572000002", now),
    )

    # --- Admin ---
    conn.execute(
        "INSERT INTO usuarios (nombre, email, password_hash, rol, telefono, creado_en) "
        "VALUES (?, ?, ?, 'admin', ?, ?)",
        ("Admin", "admin@demo.com", generate_password_hash("demo1234"), "", now),
    )


if __name__ == "__main__":
    import os
    import sqlite3

    if os.path.exists(config.DB_PATH):
        os.remove(config.DB_PATH)
    db.init_db()
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    _insertar_datos_demo(conn)
    conn.commit()
    conn.close()

    print("Base de datos creada con datos de ejemplo:")
    print("  Comercio:   comercio@demo.com   / demo1234")
    print("  Repartidor: repartidor@demo.com / demo1234")
    print("  Cliente:    cliente@demo.com    / demo1234")
    print("  Admin:      admin@demo.com      / demo1234")
