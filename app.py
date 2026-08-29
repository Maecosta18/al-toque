from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

import config
import db
import seed

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.teardown_appcontext(db.close_db)

RUTAS_PERMITIDAS_EN_MANTENIMIENTO = {"/login", "/logout", "/"}
PREFIJOS_PERMITIDOS_EN_MANTENIMIENTO = ("/admin", "/static", "/manifest.json", "/sw.js")

# Se ejecuta siempre al importar el módulo (con `python app.py` en local o
# con gunicorn en un hosting) — crea las tablas si no existen y, si la
# base está vacía (por ejemplo, un disco que se reinicia en el plan
# gratis de un hosting), carga los datos de ejemplo para que la app no
# arranque totalmente vacía.
with app.app_context():
    db.init_db()
    seed.seed_demo_si_vacio()


# ---------------------------------------------------------------- helpers

def login_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                flash("Iniciá sesión para continuar.", "error")
                return redirect(url_for("login"))
            if roles and session.get("rol") not in roles:
                flash("No tenés acceso a esa sección.", "error")
                return redirect(url_for("index"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


def current_user():
    if "user_id" not in session:
        return None
    conn = db.get_db()
    return conn.execute(
        "SELECT * FROM usuarios WHERE id = ?", (session["user_id"],)
    ).fetchone()


def mi_comercio():
    conn = db.get_db()
    return conn.execute(
        "SELECT * FROM comercios WHERE usuario_id = ?", (session["user_id"],)
    ).fetchone()


def mi_repartidor():
    conn = db.get_db()
    return conn.execute(
        "SELECT * FROM repartidores WHERE usuario_id = ?", (session["user_id"],)
    ).fetchone()


@app.before_request
def revisar_estado_global():
    if session.get("rol") == "admin":
        return None
    path = request.path
    if path in RUTAS_PERMITIDAS_EN_MANTENIMIENTO or path.startswith(PREFIJOS_PERMITIDOS_EN_MANTENIMIENTO):
        return None
    cfg = db.get_config()
    if not cfg["servicio_activo"]:
        return render_template("mantenimiento.html", mensaje=cfg["mensaje_mantenimiento"]), 503
    return None


@app.context_processor
def inject_globals():
    cfg = db.get_config()
    return {
        "current_user": current_user(),
        "zona_cobertura": cfg["zona_cobertura"],
        "dentro_de_horario": db.dentro_de_horario(cfg),
        "recargo_cancelacion_pct": cfg["recargo_cancelacion_pct"],
    }


# ---------------------------------------------------------------- home / auth

@app.route("/")
def index():
    if "user_id" in session:
        rol = session.get("rol")
        if rol == "cliente":
            return redirect(url_for("comercios"))
        if rol == "comercio":
            return redirect(url_for("comercio_pedidos"))
        if rol == "repartidor":
            return redirect(url_for("repartidor_panel"))
        if rol == "admin":
            return redirect(url_for("admin_panel"))
    return render_template("index.html")


@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        nombre = request.form["nombre"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        rol = request.form["rol"]

        if rol not in config.ROLES or rol == "admin":
            flash("Rol inválido.", "error")
            return redirect(url_for("registro"))

        conn = db.get_db()
        existente = conn.execute(
            "SELECT id FROM usuarios WHERE email = ?", (email,)
        ).fetchone()
        if existente:
            flash("Ya existe una cuenta con ese email.", "error")
            return redirect(url_for("registro"))

        cur = conn.execute(
            "INSERT INTO usuarios (nombre, email, password_hash, rol, telefono, creado_en) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (nombre, email, generate_password_hash(password), rol,
             request.form.get("telefono", ""), db.now_iso()),
        )
        usuario_id = cur.lastrowid

        if rol == "comercio":
            conn.execute(
                "INSERT INTO comercios (usuario_id, nombre, categoria, direccion) "
                "VALUES (?, ?, ?, ?)",
                (usuario_id, request.form.get("comercio_nombre", nombre),
                 request.form.get("comercio_categoria", ""),
                 request.form.get("comercio_direccion", "")),
            )
        elif rol == "repartidor":
            conn.execute(
                "INSERT INTO repartidores (usuario_id, vehiculo) VALUES (?, ?)",
                (usuario_id, request.form.get("vehiculo", "")),
            )
        conn.commit()

        session["user_id"] = usuario_id
        session["rol"] = rol
        flash("¡Cuenta creada! Bienvenido a Al Toque.", "success")
        return redirect(url_for("index"))

    return render_template("registro.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        conn = db.get_db()
        usuario = conn.execute(
            "SELECT * FROM usuarios WHERE email = ?", (email,)
        ).fetchone()
        if usuario and check_password_hash(usuario["password_hash"], password):
            if not usuario["activo"]:
                flash("Esta cuenta está suspendida. Contactá a Al Toque.", "error")
                return redirect(url_for("login"))
            session["user_id"] = usuario["id"]
            session["rol"] = usuario["rol"]
            return redirect(url_for("index"))
        flash("Email o contraseña incorrectos.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ---------------------------------------------------------------- cliente

@app.route("/comercios")
@login_required("cliente")
def comercios():
    conn = db.get_db()
    lista = conn.execute(
        "SELECT * FROM comercios WHERE activo = 1 ORDER BY nombre"
    ).fetchall()
    return render_template("cliente_comercios.html", comercios=lista)


@app.route("/comercios/<int:comercio_id>")
@login_required("cliente")
def comercio_detalle(comercio_id):
    conn = db.get_db()
    comercio = conn.execute(
        "SELECT * FROM comercios WHERE id = ?", (comercio_id,)
    ).fetchone()
    productos = conn.execute(
        "SELECT * FROM productos WHERE comercio_id = ? AND disponible = 1",
        (comercio_id,),
    ).fetchall()
    return render_template("cliente_comercio.html", comercio=comercio, productos=productos)


def _carrito():
    return session.setdefault("carrito", {})  # {producto_id(str): cantidad}


@app.route("/carrito/agregar/<int:producto_id>", methods=["POST"])
@login_required("cliente")
def carrito_agregar(producto_id):
    carrito = _carrito()
    clave = str(producto_id)
    carrito[clave] = carrito.get(clave, 0) + 1
    session.modified = True
    flash("Agregado al carrito.", "success")
    return redirect(request.referrer or url_for("comercios"))


@app.route("/carrito/quitar/<int:producto_id>", methods=["POST"])
@login_required("cliente")
def carrito_quitar(producto_id):
    carrito = _carrito()
    carrito.pop(str(producto_id), None)
    session.modified = True
    return redirect(url_for("carrito"))


@app.route("/carrito")
@login_required("cliente")
def carrito():
    conn = db.get_db()
    cfg = db.get_config()
    carrito = _carrito()
    items = []
    subtotal = 0.0
    comercio = None
    for producto_id, cantidad in carrito.items():
        producto = conn.execute(
            "SELECT * FROM productos WHERE id = ?", (producto_id,)
        ).fetchone()
        if not producto:
            continue
        if comercio is None:
            comercio = conn.execute(
                "SELECT * FROM comercios WHERE id = ?", (producto["comercio_id"],)
            ).fetchone()
        importe = producto["precio"] * cantidad
        subtotal += importe
        items.append({"producto": producto, "cantidad": cantidad, "importe": importe})

    costo_envio = cfg["costo_envio_default"] if items else 0
    total = subtotal + costo_envio
    return render_template(
        "cliente_carrito.html", items=items, subtotal=subtotal,
        costo_envio=costo_envio, total=total, comercio=comercio,
    )


@app.route("/checkout", methods=["GET", "POST"])
@login_required("cliente")
def checkout():
    carrito = _carrito()
    if not carrito:
        flash("Tu carrito está vacío.", "error")
        return redirect(url_for("comercios"))

    conn = db.get_db()
    cfg = db.get_config()

    if not db.dentro_de_horario(cfg):
        flash("Al Toque está fuera de horario de atención ahora mismo.", "error")
        return redirect(url_for("carrito"))

    if request.method == "POST":
        direccion = request.form["direccion"].strip()
        productos_rows = []
        subtotal = 0.0
        comercio_id = None
        for producto_id, cantidad in carrito.items():
            producto = conn.execute(
                "SELECT * FROM productos WHERE id = ?", (producto_id,)
            ).fetchone()
            if not producto:
                continue
            comercio_id = producto["comercio_id"]
            importe = producto["precio"] * cantidad
            subtotal += importe
            productos_rows.append((producto, cantidad))

        costo_envio = cfg["costo_envio_default"]
        comision = round(subtotal * cfg["comision_pct"], 2)
        monto_comercio = round(subtotal - comision, 2)
        total = subtotal + costo_envio

        # NOTA: acá va la integración real con Mercado Pago (checkout +
        # split de pagos). Por ahora el pedido se crea directamente como
        # "pagado" para poder probar el flujo completo end-to-end.
        cur = conn.execute(
            "INSERT INTO pedidos (cliente_id, comercio_id, estado, direccion_entrega, "
            "subtotal, costo_envio, comision_plataforma, monto_comercio, total, "
            "creado_en, actualizado_en) VALUES (?, ?, 'pagado', ?, ?, ?, ?, ?, ?, ?, ?)",
            (session["user_id"], comercio_id, direccion, subtotal, costo_envio,
             comision, monto_comercio, total, db.now_iso(), db.now_iso()),
        )
        pedido_id = cur.lastrowid
        for producto, cantidad in productos_rows:
            conn.execute(
                "INSERT INTO items_pedido (pedido_id, producto_id, nombre_producto, "
                "cantidad, precio_unitario) VALUES (?, ?, ?, ?, ?)",
                (pedido_id, producto["id"], producto["nombre"], cantidad, producto["precio"]),
            )
        conn.commit()

        session["carrito"] = {}
        session.modified = True
        flash("¡Pedido realizado! El comercio ya lo puede ver.", "success")
        return redirect(url_for("mis_pedidos"))

    return render_template("checkout.html")


@app.route("/mis-pedidos")
@login_required("cliente")
def mis_pedidos():
    conn = db.get_db()
    pedidos = conn.execute(
        "SELECT p.*, c.nombre AS comercio_nombre FROM pedidos p "
        "JOIN comercios c ON c.id = p.comercio_id "
        "WHERE p.cliente_id = ? ORDER BY p.creado_en DESC",
        (session["user_id"],),
    ).fetchall()
    return render_template("cliente_pedidos.html", pedidos=pedidos)


@app.route("/pedidos/<int:pedido_id>/seguimiento")
@login_required("cliente")
def pedido_seguimiento(pedido_id):
    conn = db.get_db()
    pedido = conn.execute(
        "SELECT p.*, c.nombre AS comercio_nombre, c.lat AS comercio_lat, c.lng AS comercio_lng "
        "FROM pedidos p JOIN comercios c ON c.id = p.comercio_id "
        "WHERE p.id = ? AND p.cliente_id = ?",
        (pedido_id, session["user_id"]),
    ).fetchone()
    if not pedido:
        flash("Pedido no encontrado.", "error")
        return redirect(url_for("mis_pedidos"))
    return render_template("seguimiento.html", pedido=pedido)


ESTADOS_CANCELABLES_POR_CLIENTE = ("pendiente_pago", "pagado", "en_preparacion", "listo_para_retirar")


@app.route("/pedidos/<int:pedido_id>/cancelar", methods=["POST"])
@login_required("cliente")
def pedido_cancelar_cliente(pedido_id):
    conn = db.get_db()
    cfg = db.get_config()
    pedido = conn.execute(
        "SELECT * FROM pedidos WHERE id = ? AND cliente_id = ?",
        (pedido_id, session["user_id"]),
    ).fetchone()
    if not pedido:
        flash("Pedido no encontrado.", "error")
        return redirect(url_for("mis_pedidos"))
    if pedido["estado"] not in ESTADOS_CANCELABLES_POR_CLIENTE:
        flash("Este pedido ya no se puede cancelar (está en camino o ya se resolvió).", "error")
        return redirect(url_for("mis_pedidos"))

    # La cancelación por parte del cliente siempre lleva recargo, sin
    # excepción (a diferencia de la cancelación por el comercio, que
    # reintegra el 100%). El % lo define el admin en Configuración.
    recargo = round(pedido["total"] * cfg["recargo_cancelacion_pct"], 2)
    reintegro = round(pedido["total"] - recargo, 2)
    conn.execute(
        "UPDATE pedidos SET estado = 'cancelado', motivo_cancelacion = ?, "
        "reintegro_cliente = ?, comision_plataforma = ?, monto_comercio = 0, "
        "actualizado_en = ? WHERE id = ?",
        ("Cancelado por el cliente (con recargo)", reintegro, recargo, db.now_iso(), pedido_id),
    )
    conn.commit()
    flash(f"Pedido cancelado. Se aplicó un recargo de ${recargo:.2f}; te corresponden ${reintegro:.2f} de reintegro.", "success")
    return redirect(url_for("mis_pedidos"))


@app.route("/pedidos/<int:pedido_id>/ubicacion")
@login_required("cliente")
def pedido_ubicacion(pedido_id):
    conn = db.get_db()
    fila = conn.execute(
        "SELECT r.ultima_lat AS lat, r.ultima_lng AS lng, r.ubicacion_en AS actualizado_en, "
        "p.estado FROM pedidos p LEFT JOIN repartidores r ON r.id = p.repartidor_id "
        "WHERE p.id = ? AND p.cliente_id = ?",
        (pedido_id, session["user_id"]),
    ).fetchone()
    if not fila:
        return jsonify({"error": "no encontrado"}), 404
    return jsonify({
        "lat": fila["lat"], "lng": fila["lng"],
        "actualizado_en": fila["actualizado_en"], "estado": fila["estado"],
    })


# ---------------------------------------------------------------- comercio

@app.route("/comercio/pedidos")
@login_required("comercio")
def comercio_pedidos():
    conn = db.get_db()
    comercio_actual = mi_comercio()
    pedidos = conn.execute(
        "SELECT * FROM pedidos WHERE comercio_id = ? ORDER BY creado_en DESC",
        (comercio_actual["id"],),
    ).fetchall()
    productos = conn.execute(
        "SELECT * FROM productos WHERE comercio_id = ? ORDER BY nombre",
        (comercio_actual["id"],),
    ).fetchall()
    return render_template(
        "comercio_dashboard.html", comercio=comercio_actual, pedidos=pedidos, productos=productos
    )


@app.route("/comercio/productos/nuevo", methods=["POST"])
@login_required("comercio")
def comercio_producto_nuevo():
    conn = db.get_db()
    comercio_actual = mi_comercio()
    conn.execute(
        "INSERT INTO productos (comercio_id, nombre, descripcion, precio) VALUES (?, ?, ?, ?)",
        (comercio_actual["id"], request.form["nombre"], request.form.get("descripcion", ""),
         float(request.form["precio"])),
    )
    conn.commit()
    flash("Producto agregado.", "success")
    return redirect(url_for("comercio_pedidos"))


@app.route("/comercio/productos/<int:producto_id>/editar", methods=["POST"])
@login_required("comercio")
def comercio_producto_editar(producto_id):
    conn = db.get_db()
    comercio_actual = mi_comercio()
    producto = conn.execute(
        "SELECT * FROM productos WHERE id = ? AND comercio_id = ?",
        (producto_id, comercio_actual["id"]),
    ).fetchone()
    if not producto:
        flash("Producto no encontrado.", "error")
        return redirect(url_for("comercio_pedidos"))
    conn.execute(
        "UPDATE productos SET nombre = ?, descripcion = ?, precio = ?, disponible = ? WHERE id = ?",
        (request.form["nombre"], request.form.get("descripcion", ""),
         float(request.form["precio"]), 1 if request.form.get("disponible") else 0, producto_id),
    )
    conn.commit()
    flash("Producto actualizado.", "success")
    return redirect(url_for("comercio_pedidos"))


@app.route("/comercio/productos/<int:producto_id>/eliminar", methods=["POST"])
@login_required("comercio")
def comercio_producto_eliminar(producto_id):
    conn = db.get_db()
    comercio_actual = mi_comercio()
    producto = conn.execute(
        "SELECT * FROM productos WHERE id = ? AND comercio_id = ?",
        (producto_id, comercio_actual["id"]),
    ).fetchone()
    if not producto:
        flash("Producto no encontrado.", "error")
        return redirect(url_for("comercio_pedidos"))
    try:
        conn.execute("DELETE FROM productos WHERE id = ?", (producto_id,))
        conn.commit()
        flash("Producto eliminado.", "success")
    except db.sqlite3.IntegrityError:
        conn.rollback()
        # Tiene pedidos históricos asociados: no se puede borrar sin
        # perder esos registros, así que se oculta en vez de eliminarlo.
        conn.execute("UPDATE productos SET disponible = 0 WHERE id = ?", (producto_id,))
        conn.commit()
        flash("Ese producto ya tiene pedidos asociados, así que no se puede borrar del todo — lo oculté de la lista.", "success")
    return redirect(url_for("comercio_pedidos"))


@app.route("/comercio/ubicacion", methods=["POST"])
@login_required("comercio")
def comercio_ubicacion():
    datos = request.get_json(silent=True) or {}
    lat, lng = datos.get("lat"), datos.get("lng")
    if lat is None or lng is None:
        return jsonify({"ok": False, "error": "faltan coordenadas"}), 400
    conn = db.get_db()
    comercio_actual = mi_comercio()
    conn.execute("UPDATE comercios SET lat = ?, lng = ? WHERE id = ?", (lat, lng, comercio_actual["id"]))
    conn.commit()
    return jsonify({"ok": True})


@app.route("/comercio/pedidos/<int:pedido_id>/estado", methods=["POST"])
@login_required("comercio")
def comercio_cambiar_estado(pedido_id):
    nuevo_estado = request.form["estado"]
    conn = db.get_db()

    if nuevo_estado == "cancelado":
        pedido = conn.execute("SELECT * FROM pedidos WHERE id = ?", (pedido_id,)).fetchone()
        motivo = request.form.get("motivo", "")
        # Cancelación justificada: se reintegra el total al cliente y se
        # anula la comisión retenida (según la política definida para el piloto).
        conn.execute(
            "UPDATE pedidos SET estado = ?, motivo_cancelacion = ?, "
            "reintegro_cliente = ?, comision_plataforma = 0, actualizado_en = ? "
            "WHERE id = ?",
            (nuevo_estado, motivo, pedido["total"], db.now_iso(), pedido_id),
        )
    elif nuevo_estado in config.ESTADOS_PEDIDO:
        conn.execute(
            "UPDATE pedidos SET estado = ?, actualizado_en = ? WHERE id = ?",
            (nuevo_estado, db.now_iso(), pedido_id),
        )
    conn.commit()
    return redirect(url_for("comercio_pedidos"))


# ---------------------------------------------------------------- repartidor

@app.route("/repartidor")
@login_required("repartidor")
def repartidor_panel():
    conn = db.get_db()
    repartidor_actual = mi_repartidor()
    disponibles = conn.execute(
        "SELECT p.*, c.nombre AS comercio_nombre, c.direccion AS comercio_direccion "
        "FROM pedidos p JOIN comercios c ON c.id = p.comercio_id "
        "WHERE p.estado = 'listo_para_retirar' AND p.repartidor_id IS NULL "
        "ORDER BY p.creado_en"
    ).fetchall()
    mis_entregas = conn.execute(
        "SELECT p.*, c.nombre AS comercio_nombre, c.direccion AS comercio_direccion "
        "FROM pedidos p JOIN comercios c ON c.id = p.comercio_id "
        "WHERE p.repartidor_id = ? AND p.estado NOT IN ('entregado', 'cancelado') "
        "ORDER BY p.creado_en",
        (repartidor_actual["id"],),
    ).fetchall()
    return render_template(
        "repartidor_panel.html", disponibles=disponibles, mis_entregas=mis_entregas,
        compartiendo=bool(repartidor_actual["ultima_lat"]),
    )


@app.route("/repartidor/ubicacion", methods=["POST"])
@login_required("repartidor")
def repartidor_ubicacion():
    datos = request.get_json(silent=True) or {}
    lat, lng = datos.get("lat"), datos.get("lng")
    if lat is None or lng is None:
        return jsonify({"ok": False, "error": "faltan coordenadas"}), 400
    conn = db.get_db()
    repartidor_actual = mi_repartidor()
    ahora = db.now_iso()
    conn.execute(
        "UPDATE repartidores SET ultima_lat = ?, ultima_lng = ?, ubicacion_en = ? WHERE id = ?",
        (lat, lng, ahora, repartidor_actual["id"]),
    )
    # Deja asentado el registro histórico de ubicación para cada pedido
    # que este repartidor tiene en camino ahora mismo (auditoría / admin).
    entregas_activas = conn.execute(
        "SELECT id FROM pedidos WHERE repartidor_id = ? AND estado = 'en_camino'",
        (repartidor_actual["id"],),
    ).fetchall()
    for entrega in entregas_activas:
        conn.execute(
            "INSERT INTO ubicaciones_pedido (pedido_id, repartidor_id, lat, lng, creado_en) "
            "VALUES (?, ?, ?, ?, ?)",
            (entrega["id"], repartidor_actual["id"], lat, lng, ahora),
        )
    conn.commit()
    return jsonify({"ok": True})


@app.route("/repartidor/pedidos/<int:pedido_id>/aceptar", methods=["POST"])
@login_required("repartidor")
def repartidor_aceptar(pedido_id):
    conn = db.get_db()
    repartidor_actual = mi_repartidor()
    conn.execute(
        "UPDATE pedidos SET repartidor_id = ?, estado = 'en_camino', actualizado_en = ? "
        "WHERE id = ? AND repartidor_id IS NULL",
        (repartidor_actual["id"], db.now_iso(), pedido_id),
    )
    conn.commit()
    return redirect(url_for("repartidor_panel"))


@app.route("/repartidor/pedidos/<int:pedido_id>/entregar", methods=["POST"])
@login_required("repartidor")
def repartidor_entregar(pedido_id):
    conn = db.get_db()
    conn.execute(
        "UPDATE pedidos SET estado = 'entregado', actualizado_en = ? WHERE id = ?",
        (db.now_iso(), pedido_id),
    )
    conn.commit()
    return redirect(url_for("repartidor_panel"))


@app.route("/repartidor/ganancias")
@login_required("repartidor")
def repartidor_ganancias():
    conn = db.get_db()
    repartidor_actual = mi_repartidor()
    entregas = conn.execute(
        "SELECT p.*, c.nombre AS comercio_nombre FROM pedidos p "
        "JOIN comercios c ON c.id = p.comercio_id "
        "WHERE p.repartidor_id = ? AND p.estado = 'entregado' "
        "ORDER BY p.actualizado_en DESC",
        (repartidor_actual["id"],),
    ).fetchall()
    total = sum(e["costo_envio"] for e in entregas)
    return render_template("repartidor_ganancias.html", entregas=entregas, total=total)


# ---------------------------------------------------------------- admin

@app.route("/admin")
@login_required("admin")
def admin_panel():
    conn = db.get_db()
    resumen = conn.execute(
        "SELECT COUNT(*) AS pedidos_totales, "
        "COALESCE(SUM(comision_plataforma), 0) AS comision_total, "
        "COALESCE(SUM(total), 0) AS ventas_totales "
        "FROM pedidos WHERE estado != 'cancelado'"
    ).fetchone()
    comercios_activos = conn.execute("SELECT COUNT(*) AS n FROM comercios WHERE activo = 1").fetchone()["n"]
    repartidores_activos = conn.execute(
        "SELECT COUNT(*) AS n FROM repartidores r JOIN usuarios u ON u.id = r.usuario_id WHERE u.activo = 1"
    ).fetchone()["n"]
    ultimos_pedidos = conn.execute(
        "SELECT p.*, c.nombre AS comercio_nombre FROM pedidos p "
        "JOIN comercios c ON c.id = p.comercio_id ORDER BY p.creado_en DESC LIMIT 20"
    ).fetchall()
    cfg = db.get_config()
    return render_template(
        "admin_dashboard.html", resumen=resumen, comercios_activos=comercios_activos,
        repartidores_activos=repartidores_activos, ultimos_pedidos=ultimos_pedidos, cfg=cfg,
    )


@app.route("/admin/comercios")
@login_required("admin")
def admin_comercios():
    conn = db.get_db()
    lista = conn.execute(
        "SELECT c.*, u.nombre AS owner_nombre, u.email AS owner_email, "
        "u.telefono AS owner_telefono, u.activo AS owner_activo, u.id AS owner_id "
        "FROM comercios c JOIN usuarios u ON u.id = c.usuario_id ORDER BY c.nombre"
    ).fetchall()
    return render_template("admin_comercios.html", comercios=lista)


@app.route("/admin/comercios/<int:comercio_id>/editar", methods=["POST"])
@login_required("admin")
def admin_comercio_editar(comercio_id):
    conn = db.get_db()
    lat = request.form.get("lat") or None
    lng = request.form.get("lng") or None
    conn.execute(
        "UPDATE comercios SET nombre = ?, categoria = ?, direccion = ?, lat = ?, lng = ? WHERE id = ?",
        (request.form["nombre"], request.form.get("categoria", ""),
         request.form.get("direccion", ""), lat, lng, comercio_id),
    )
    conn.commit()
    flash("Comercio actualizado.", "success")
    return redirect(url_for("admin_comercios"))


@app.route("/admin/comercios/<int:comercio_id>/toggle", methods=["POST"])
@login_required("admin")
def admin_comercio_toggle(comercio_id):
    conn = db.get_db()
    conn.execute("UPDATE comercios SET activo = 1 - activo WHERE id = ?", (comercio_id,))
    conn.commit()
    return redirect(url_for("admin_comercios"))


@app.route("/admin/clientes")
@login_required("admin")
def admin_clientes():
    conn = db.get_db()
    lista = conn.execute(
        "SELECT * FROM usuarios WHERE rol = 'cliente' ORDER BY creado_en DESC"
    ).fetchall()
    return render_template("admin_clientes.html", clientes=lista)


@app.route("/admin/repartidores")
@login_required("admin")
def admin_repartidores():
    conn = db.get_db()
    lista = conn.execute(
        "SELECT r.*, u.nombre AS nombre, u.email AS email, u.telefono AS telefono, "
        "u.activo AS activo, u.id AS usuario_id "
        "FROM repartidores r JOIN usuarios u ON u.id = r.usuario_id ORDER BY u.nombre"
    ).fetchall()
    return render_template("admin_repartidores.html", repartidores=lista)


@app.route("/admin/usuarios/<int:usuario_id>/toggle", methods=["POST"])
@login_required("admin")
def admin_usuario_toggle(usuario_id):
    conn = db.get_db()
    conn.execute("UPDATE usuarios SET activo = 1 - activo WHERE id = ?", (usuario_id,))
    conn.commit()
    return redirect(request.referrer or url_for("admin_panel"))


@app.route("/admin/usuarios/<int:usuario_id>/editar", methods=["POST"])
@login_required("admin")
def admin_usuario_editar(usuario_id):
    conn = db.get_db()
    try:
        conn.execute(
            "UPDATE usuarios SET nombre = ?, email = ?, telefono = ? WHERE id = ?",
            (request.form["nombre"].strip(), request.form["email"].strip().lower(),
             request.form.get("telefono", ""), usuario_id),
        )
        conn.commit()
        flash("Datos actualizados.", "success")
    except db.sqlite3.IntegrityError:
        conn.rollback()
        flash("Ya existe otra cuenta con ese email.", "error")
    return redirect(request.referrer or url_for("admin_panel"))


@app.route("/admin/repartidores/<int:repartidor_id>/editar", methods=["POST"])
@login_required("admin")
def admin_repartidor_editar(repartidor_id):
    conn = db.get_db()
    repartidor_fila = conn.execute("SELECT * FROM repartidores WHERE id = ?", (repartidor_id,)).fetchone()
    if not repartidor_fila:
        flash("Repartidor no encontrado.", "error")
        return redirect(url_for("admin_repartidores"))
    try:
        conn.execute(
            "UPDATE usuarios SET nombre = ?, email = ?, telefono = ? WHERE id = ?",
            (request.form["nombre"].strip(), request.form["email"].strip().lower(),
             request.form.get("telefono", ""), repartidor_fila["usuario_id"]),
        )
        conn.execute(
            "UPDATE repartidores SET vehiculo = ? WHERE id = ?",
            (request.form.get("vehiculo", ""), repartidor_id),
        )
        conn.commit()
        flash("Datos del repartidor actualizados.", "success")
    except db.sqlite3.IntegrityError:
        conn.rollback()
        flash("Ya existe otra cuenta con ese email.", "error")
    return redirect(url_for("admin_repartidores"))


@app.route("/admin/configuracion", methods=["GET", "POST"])
@login_required("admin")
def admin_configuracion():
    conn = db.get_db()
    if request.method == "POST":
        conn.execute(
            "UPDATE configuracion SET comision_pct = ?, costo_envio_default = ?, "
            "zona_cobertura = ?, horario_semana_inicio = ?, horario_semana_fin = ?, "
            "recargo_cancelacion_pct = ?, mensaje_mantenimiento = ? WHERE id = 1",
            (
                float(request.form["comision_pct"]) / 100,
                float(request.form["costo_envio_default"]),
                request.form["zona_cobertura"].strip(),
                request.form["horario_semana_inicio"],
                request.form["horario_semana_fin"],
                float(request.form["recargo_cancelacion_pct"]) / 100,
                request.form["mensaje_mantenimiento"].strip(),
            ),
        )
        conn.commit()
        flash("Configuración actualizada.", "success")
        return redirect(url_for("admin_configuracion"))
    cfg = db.get_config()
    return render_template("admin_configuracion.html", cfg=cfg)


@app.route("/admin/pedidos/<int:pedido_id>")
@login_required("admin")
def admin_pedido_detalle(pedido_id):
    conn = db.get_db()
    pedido = conn.execute(
        "SELECT p.*, c.nombre AS comercio_nombre, c.lat AS comercio_lat, c.lng AS comercio_lng, "
        "cl.nombre AS cliente_nombre, cl.telefono AS cliente_telefono, "
        "r.vehiculo AS repartidor_vehiculo, ru.nombre AS repartidor_nombre "
        "FROM pedidos p "
        "JOIN comercios c ON c.id = p.comercio_id "
        "JOIN usuarios cl ON cl.id = p.cliente_id "
        "LEFT JOIN repartidores r ON r.id = p.repartidor_id "
        "LEFT JOIN usuarios ru ON ru.id = r.usuario_id "
        "WHERE p.id = ?",
        (pedido_id,),
    ).fetchone()
    if not pedido:
        flash("Pedido no encontrado.", "error")
        return redirect(url_for("admin_panel"))
    items = conn.execute(
        "SELECT * FROM items_pedido WHERE pedido_id = ?", (pedido_id,)
    ).fetchall()
    historial = conn.execute(
        "SELECT * FROM ubicaciones_pedido WHERE pedido_id = ? ORDER BY creado_en",
        (pedido_id,),
    ).fetchall()
    distancia_km = None
    if pedido["comercio_lat"] and historial:
        distancia_km = db.haversine_km(
            pedido["comercio_lat"], pedido["comercio_lng"],
            historial[-1]["lat"], historial[-1]["lng"],
        )
    return render_template(
        "admin_pedido_detalle.html", pedido=pedido, items=items,
        historial=historial, distancia_km=distancia_km,
    )


@app.route("/admin/servicio/toggle", methods=["POST"])
@login_required("admin")
def admin_servicio_toggle():
    conn = db.get_db()
    cfg = db.get_config()
    if cfg["servicio_activo"]:
        confirmacion = request.form.get("confirmacion", "")
        if confirmacion.strip().upper() != "SUSPENDER":
            flash('Para suspender el servicio, escribí "SUSPENDER" tal cual en el campo de confirmación.', "error")
            return redirect(url_for("admin_configuracion"))
        conn.execute("UPDATE configuracion SET servicio_activo = 0 WHERE id = 1")
        conn.commit()
        flash("Al Toque quedó fuera de servicio para todos los usuarios.", "error")
    else:
        conn.execute("UPDATE configuracion SET servicio_activo = 1 WHERE id = 1")
        conn.commit()
        flash("Al Toque volvió a estar activo.", "success")
    return redirect(url_for("admin_configuracion"))


# ---------------------------------------------------------------- PWA

@app.route("/manifest.json")
def manifest():
    return app.send_static_file("manifest.json")


@app.route("/sw.js")
def service_worker():
    return app.send_static_file("sw.js")


if __name__ == "__main__":
    # La inicialización de la base de datos y la carga de datos de ejemplo
    # ya se hacen arriba, al importar el módulo (necesario para que
    # funcionen también con gunicorn en un hosting). Acá solo falta
    # levantar el servidor de desarrollo para probar en la máquina local.
    app.run(debug=True, host="0.0.0.0", port=5000)
