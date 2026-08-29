# Al Toque — prototipo

Prototipo funcional del marketplace + delivery para Río Segundo y Pilar.
Es una web app (PWA) que se abre desde el navegador del celular, sin
costos de tiendas de apps.

**Stack**: Python (Flask) + SQLite, sin dependencias externas más allá de
Flask (todo lo demás son librerías que ya vienen con Python).
Nota: se armó así porque, al momento de programarlo, el entorno de Claude
no tenía acceso a los repositorios de paquetes de Node (npm) para usar
Next.js/React como se había planteado al principio. Este stack cumple el
mismo objetivo para un piloto de bajo presupuesto.

## Cómo correrlo

**En Windows, la forma más fácil**: hacé doble clic en `instalar_y_abrir.bat`.
Instala lo necesario, carga los datos de ejemplo y abre el navegador solo.
Dejá la ventana negra abierta mientras la usás.

**Manual (cualquier sistema operativo):**

```bash
pip install -r requirements.txt
python3 seed.py        # crea la base de datos con datos de ejemplo
python3 app.py          # arranca el servidor en http://localhost:5000
```

Usuarios de prueba (contraseña `demo1234` para todos):

- Comercio: `comercio@demo.com`
- Repartidor: `repartidor@demo.com`
- Cliente: `cliente@demo.com`
- Admin: `admin@demo.com`

Desde el celu, si accedés a la web app y usás "Agregar a pantalla de
inicio" en el navegador, queda instalada como una app normal (es una PWA).

## Qué incluye este prototipo

- Registro y login con 4 roles: cliente, comercio, repartidor, admin.
- Cliente: ver comercios, ver productos, armar carrito, confirmar pedido,
  **cancelar un pedido (con recargo obligatorio, ver más abajo)**.
- Comercio: ver pedidos entrantes, cambiar de estado (preparando, listo,
  cancelar con motivo), **cargar, editar precio/datos y eliminar
  productos** (si el producto ya tiene pedidos asociados, en vez de
  borrarlo se oculta de la venta para no perder el historial), y
  **configurar su ubicación** (con el GPS del navegador) para que los
  clientes vean la distancia.
- Repartidor: ver entregas disponibles **mostrando cuánto va a cobrar
  antes de aceptar**, aceptar una, marcarla entregada.
- Admin: resumen de pedidos, comisión acumulada, comercios y repartidores.
- Chequeo de horario de atención (08:00–01:00 entre semana, 24 hs
  sábados y domingos) — fuera de horario no se puede confirmar un pedido.
- Cálculo de split: comisión de la plataforma sobre el subtotal, el
  resto para el comercio, el envío completo para el repartidor.
- Cancelación con reintegro: si el comercio cancela, se reintegra el
  total al cliente y se anula la comisión retenida.
- **Seguimiento en vivo por GPS**: el repartidor activa "Compartir mi
  ubicación" desde su panel (usa la geolocalización del navegador) y el
  cliente ve, en un mismo mapa, la posición del **comercio** (fija) y
  del **repartidor** (en vivo, actualizando cada 8 segundos), más la
  distancia en línea recta entre el repartidor y su propia ubicación.
  El mapa es gratuito (OpenStreetMap) — no usa Google Maps, ver la nota
  más abajo.
- **Distancia al comercio**: al entrar a un comercio, si configuró su
  ubicación, el cliente ve a cuántos km está (línea recta, no ruta por
  calle) usando su propia geolocalización.
- **Cancelación del cliente con recargo obligatorio**: el cliente puede
  cancelar su pedido mientras no esté "en camino"; siempre se le
  descuenta un recargo (el % lo define el admin en Configuración,
  10% por defecto) y se le informa el monto antes de confirmar. Es
  distinta de la cancelación por el comercio, que sigue reintegrando el
  100%.
- **Ganancias del repartidor**: cada pedido (disponible o en curso)
  muestra cuánto va a cobrar el repartidor antes de aceptarlo, y hay
  una pantalla de "Mis ganancias" con el acumulado histórico de
  entregas completadas.
- **Panel admin con control total**: tarjetas grandes en la pantalla
  principal para entrar directo a gestionar comercios, clientes,
  repartidores y configuración. Para cada uno se puede **editar
  nombre, email y teléfono** (y vehículo en el caso del repartidor),
  además de suspender/reactivar la cuenta — no es solo un
  activar/desactivar, es edición completa. También hay configuración
  de la plataforma (comisión, costo de envío, recargo por cancelación,
  zona de cobertura, horario) editable desde la web, sin tocar código.
- **Registro histórico de ubicaciones**: cada vez que un repartidor
  comparte su posición mientras tiene un pedido en camino, queda
  guardada (no se pisa, se acumula). Desde el detalle de un pedido en
  el panel admin (clickeando cualquier pedido en "Últimos pedidos") se
  ve el trayecto completo en el mapa y la lista de posiciones con
  fecha y hora.
- **Botón de emergencia**: desde Configuración, el admin puede "bajar
  la app de servicio" (con confirmación escribiendo "SUSPENDER"). Con
  el servicio suspendido, clientes/comercios/repartidores ven una
  pantalla de mantenimiento y no pueden operar; el admin mantiene
  acceso total para poder reactivarlo.

### Nota sobre el mapa (OpenStreetMap, no Google Maps)

Pediste específicamente GPS "de Google Maps", pero usar la API de
Google Maps requiere que crees una cuenta de Google Cloud con una
tarjeta cargada (tiene una cuota gratuita mensual, pero no funciona sin
facturación activada). Dado el presupuesto del piloto, lo dejé con
OpenStreetMap, que es 100% gratis y no requiere cuenta ni API key —
cumple lo mismo (ubicación en vivo, distancias) salvo la ruta exacta
por calles, que acá se calcula en línea recta. Si más adelante querés
pasar a Google Maps (rutas reales, tráfico en vivo), avisame y lo
integro — vos vas a tener que crear la cuenta y pasarme la API key.

## Cómo publicarla (link público, plan gratis de Render)

Elegiste empezar con el **plan gratis de Render** para probar el link
público. Es gratis y no pide tarjeta, pero tiene dos límites que conviene
tener claros antes de mandarle el link a alguien:

- **Se "duerme" a los 15 minutos sin uso.** El primer acceso después de
  estar dormida tarda unos 30-60 segundos en responder (se está
  despertando); después va normal hasta que vuelve a estar 15 min sin uso.
- **El disco NO es persistente.** Cada vez que el servicio se reinicia
  (por dormirse y despertar, o cada vez que subís un cambio) se borra la
  base de datos entera y se recarga sola con los datos de ejemplo. Es
  decir: **pedidos, productos nuevos, usuarios nuevos que se hayan
  creado se pierden** en cada reinicio. Para un piloto real con datos
  que duren, más adelante hay que pasar a un plan pago con disco
  persistente (~USD 7/mes + USD 0.25/GB de disco) — avisame cuando
  llegue ese momento y lo configuro.

Pasos para publicarla:

1. **Crear una cuenta gratis en GitHub** (si no tenés): https://github.com/signup
2. **Crear un repositorio nuevo** (por ejemplo `al-toque`) y subir el
   contenido de esta carpeta. La forma más fácil sin usar la terminal:
   entrá al repo nuevo en GitHub → "Add file" → "Upload files" → arrastrá
   todos los archivos y carpetas del proyecto (descomprimí el .zip
   primero) → "Commit changes".
3. **Crear una cuenta gratis en Render**: https://render.com (podés
   entrar directo con tu cuenta de GitHub).
4. En el dashboard de Render: **"New +" → "Blueprint"** → elegí el
   repositorio `al-toque` que subiste. Render va a detectar el archivo
   `render.yaml` que ya está en el proyecto y va a dejar todo
   configurado solo (plan gratis, comando de build, comando de arranque
   y una clave secreta generada automáticamente) — solo tenés que
   confirmar con "Apply".
   - Si preferís hacerlo a mano en vez de con el Blueprint: "New +" →
     "Web Service" → elegí el repo → Runtime: Python → Build Command:
     `pip install -r requirements.txt` → Start Command: `gunicorn app:app`
     → Plan: Free → agregá una variable de entorno `AL_TOQUE_SECRET_KEY`
     con cualquier texto largo y random como valor.
5. Esperá unos minutos a que termine el primer deploy. Render te va a dar
   una URL pública tipo `https://al-toque.onrender.com` — ese es el link
   que le podés pasar a quien quieras para que pruebe la app, con los
   mismos usuarios de prueba (`demo1234` para todos).

Cuando quieras subir un cambio nuevo (por ejemplo si te ayudo a agregar
algo más), es tan simple como volver a subir los archivos actualizados a
GitHub — Render redespliega solo.

## Lo que falta para el piloto real (próximos pasos)

1. **Integrar Mercado Pago de verdad.** Hoy el checkout simula el pago
   (crea el pedido como "pagado" directamente). Falta conectar el
   Checkout Pro o Checkout API de Mercado Pago con **split de pagos**
   (Mercado Pago tiene un producto específico para marketplaces que
   permite repartir un cobro entre varias cuentas).
2. **Notificaciones**: hoy no hay avisos cuando cambia el estado de un
   pedido (ni al cliente, ni al repartidor). Como mínimo conviene sumar
   notificaciones push de la PWA; más adelante, WhatsApp.
3. **GPS real en producción**: el seguimiento usa la geolocalización
   del navegador del repartidor, así que solo funciona mientras tiene
   la pestaña abierta y activada — para algo más robusto en el futuro
   (seguimiento en segundo plano) hay que empaquetarla como app nativa
   o usar una PWA con permisos de ubicación en background. El mapa usa
   OpenStreetMap gratis; para un uso más intensivo en producción
   conviene pasar a un proveedor de mapas de pago (Mapbox, MapTiler).
4. **Dirección de entrega sin geocodificar**: la dirección del cliente
   sigue siendo texto libre — no hay un pin exacto del destino en el
   mapa (sí hay pin del comercio y del repartidor en vivo).
5. **Hosting**: ya está publicada en el plan gratis de Render (ver
   sección "Cómo publicarla" arriba). Cuando el piloto necesite guardar
   datos reales sin perderlos en cada reinicio, pasar al plan pago de
   Render con disco persistente (~USD 7/mes + USD 0.25/GB) o a una base
   de datos administrada.
6. **Seguridad**: antes de un lanzamiento real, cambiar `SECRET_KEY` en
   `config.py` por una clave generada y no versionarla en el código.

## Estructura del proyecto

```
app.py              rutas y lógica de la aplicación
config.py           configuración (horario, comisión, zona de cobertura)
db.py                acceso a la base de datos SQLite
seed.py              carga de datos de ejemplo
render.yaml          configuración para publicar en Render (plan gratis)
templates/           páginas HTML (Jinja2)
static/css/          estilos (marca Al Toque: fondo oscuro, rayo naranja)
static/img/          logo
static/icons/        íconos para la PWA
static/manifest.json  configuración de instalación como app
static/sw.js          service worker (para que funcione como PWA)
```
