from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required
import csv
import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta'  # Cambia esto a una clave secreta segura
login_manager = LoginManager()
login_manager.init_app(app)

# Rutas de archivos
USUARIOS_PATH = 'data/usuarios.csv'
INVENTARIO_PATH = 'data/inventario.csv'
CLIENTES_PATH = 'data/clientes.csv'
PROVEEDORES_PATH = 'data/proveedores.csv'
VENTAS_PATH = 'data/ventas.csv'  # Ruta para las ventas

# Almacenar información de la caja
ventas_del_dia = []
fecha_apertura = None

class User(UserMixin):
    def __init__(self, id, rol):
        self.id = id
        self.rol = rol

@login_manager.user_loader
def load_user(user_id):
    usuarios = cargar_usuarios()
    usuario = next((user for user in usuarios if user['ID'] == user_id), None)
    return User(usuario['ID'], usuario['Rol']) if usuario else None

def cargar_csv(path):
    datos = []
    try:
        if os.path.exists(path):
            with open(path, mode='r', newline='') as file:
                reader = csv.DictReader(file)
                datos = [row for row in reader]
    except Exception as e:
        print(f"Error al cargar datos de {path}: {e}")
    return datos

def cargar_usuarios():
    return cargar_csv(USUARIOS_PATH)

def cargar_inventario():
    return cargar_csv(INVENTARIO_PATH)

def cargar_clientes():
    return cargar_csv(CLIENTES_PATH)

def cargar_proveedores():
    return cargar_csv(PROVEEDORES_PATH)

def cargar_ventas():
    return cargar_csv(VENTAS_PATH)

def verificar_stock_bajo(inventario):
    alertas = []
    for producto in inventario:
        try:
            cantidad = int(producto['Cantidad']) if producto['Cantidad'] else 0
            umbral = int(producto['Umbral']) if producto['Umbral'] else 0
            if cantidad < umbral:
                alertas.append(producto)
        except (ValueError, TypeError):
            print(f"Error al procesar el producto {producto['Nombre']}: Cantidad o Umbral no válidos.")
    return alertas

@app.route('/')
def inicio():
    return redirect(url_for('inicio_sesion'))

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        email = request.form['email'].strip()
        password = request.form['password'].strip()
        rol = request.form['rol'].strip()
        
        if not email or not password or not rol:
            flash('Todos los campos son obligatorios', 'error')
            return redirect(url_for('registro'))
        
        roles_permitidos = ['usuario', 'admin']
        if rol not in roles_permitidos:
            flash('Rol no válido. Debe ser "usuario" o "admin".', 'error')
            return redirect(url_for('registro'))

        usuarios = cargar_usuarios()
        if any(user['Email'] == email for user in usuarios):
            flash('El email ya está en uso.', 'error')
            return redirect(url_for('registro'))

        nuevo_id = len(usuarios) + 1  # Calcula el nuevo ID
        try:
            with open(USUARIOS_PATH, mode='a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow([nuevo_id, email, password, rol])
            flash('Registro exitoso. Puedes iniciar sesión ahora.', 'success')
            return redirect(url_for('inicio_sesion'))
        except Exception as e:
            flash(f'Error al registrar el usuario: {e}', 'error')
            return redirect(url_for('registro'))

    return render_template('registro.html')

@app.route('/inicio_sesion', methods=['GET', 'POST'])
def inicio_sesion():
    if request.method == 'POST':
        email = request.form['email'].strip()
        password = request.form['password'].strip()
        if not email or not password:
            flash('Todos los campos son obligatorios.', 'error')
            return redirect(url_for('inicio_sesion'))

        usuarios = cargar_usuarios()
        usuario = next((user for user in usuarios if user['Email'] == email), None)

        if usuario and usuario['Password'] == password:
            user = User(usuario['ID'], usuario['Rol'])
            login_user(user)
            flash('Inicio de sesión exitoso.', 'success')
            return redirect(url_for('pagina_principal'))
        else:
            flash('Credenciales incorrectas.', 'error')
            return redirect(url_for('inicio_sesion'))
    return render_template('inicio_sesion.html')

@app.route('/pagina_principal')
@login_required
def pagina_principal():
    inventario = cargar_inventario()
    alertas = verificar_stock_bajo(inventario)
    return render_template('pagina_principal.html', alertas=alertas)

@app.route('/cerrar_sesion', methods=['POST'])
@login_required
def cerrar_sesion():
    logout_user()
    flash('Has cerrado sesión.', 'success')
    return redirect(url_for('inicio_sesion'))

# Rutas de gestión de inventario
@app.route('/inventario', methods=['GET'])
@login_required
def home():
    inventario = cargar_inventario()
    busqueda = request.args.get('busqueda')
    if busqueda:
        inventario = [producto for producto in inventario if busqueda.lower() in producto['Nombre'].lower()]
    return render_template('index.html', inventario=inventario)

@app.route('/agregar', methods=['GET', 'POST'])
@login_required
def agregar_producto():
    if request.method == 'POST':
        nombre = request.form['nombre']
        categoria = request.form['categoria']
        cantidad = request.form['cantidad']
        precio = request.form['precio']
        
        if not nombre or not categoria or not cantidad or not precio:
            flash('Todos los campos son obligatorios', 'error')
            return redirect(url_for('agregar_producto'))
        
        try:
            cantidad = int(cantidad)
            precio = float(precio)
            if cantidad < 0 or precio < 0:
                flash('La cantidad y el precio deben ser números positivos', 'error')
                return redirect(url_for('agregar_producto'))
        except ValueError:
            flash('La cantidad y el precio deben ser números válidos', 'error')
            return redirect(url_for('agregar_producto'))

        umbral = int(cantidad * 0.2)

        inventario = cargar_inventario()
        nuevo_id = max(int(item['ID']) for item in inventario) + 1 if inventario else 1

        try:
            with open(INVENTARIO_PATH, mode='a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow([nuevo_id, nombre, categoria, cantidad, precio, umbral])
            flash('Producto agregado exitosamente.', 'success')
            return redirect(url_for('home'))
        except Exception as e:
            flash(f'Error al agregar el producto: {e}', 'error')
            return redirect(url_for('agregar_producto'))
    
    return render_template('agregar_producto.html')

@app.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_producto(id):
    inventario = cargar_inventario()
    producto = next((item for item in inventario if int(item['ID']) == id), None)
    
    if not producto:
        flash('Producto no encontrado.', 'error')
        return redirect(url_for('home'))

    if request.method == 'POST':
        nombre = request.form['nombre']
        categoria = request.form['categoria']
        cantidad = request.form['cantidad']
        precio = request.form['precio']
        
        if not nombre or not categoria or not cantidad or not precio:
            flash('Todos los campos son obligatorios', 'error')
            return redirect(url_for('editar_producto', id=id))

        try:
            cantidad = int(cantidad)
            precio = float(precio)
            if cantidad < 0 or precio < 0:
                flash('La cantidad y el precio deben ser números positivos', 'error')
                return redirect(url_for('editar_producto', id=id))
        except ValueError:
            flash('La cantidad y el precio deben ser números válidos', 'error')
            return redirect(url_for('editar_producto', id=id))

        umbral = int(cantidad * 0.2)
        
        # Actualizando el producto
        producto.update({
            'Nombre': nombre,
            'Categoria': categoria,
            'Cantidad': cantidad,
            'Precio': precio,
            'Umbral': umbral
        })
        
        try:
            with open(INVENTARIO_PATH, mode='w', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=producto.keys())
                writer.writeheader()
                writer.writerows(inventario)
            flash('Producto editado exitosamente.', 'success')
            return redirect(url_for('home'))
        except Exception as e:
            flash(f'Error al editar el producto: {e}', 'error')
    
    return render_template('editar_producto.html', producto=producto)

@app.route('/eliminar/<int:id>')
@login_required
def eliminar_producto(id):
    inventario = cargar_inventario()
    if 0 < id <= len(inventario):
        inventario.pop(id - 1)
        try:
            with open(INVENTARIO_PATH, mode='w', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=inventario[0].keys())
                writer.writeheader()
                writer.writerows(inventario)
            flash('Producto eliminado exitosamente.', 'success')
        except Exception as e:
            flash(f'Error al eliminar el producto: {e}', 'error')
    else:
        flash('ID de producto no válido.', 'error')
    return redirect(url_for('home'))

@app.route('/vender', methods=['GET', 'POST'])
@login_required
def vender_producto():
    inventario = cargar_inventario()
    if request.method == 'POST':
        productos_vendidos = request.form.getlist('productos')
        cantidades_vendidas = request.form.getlist('cantidades')
        actualizaciones = {}

        for index, id_producto in enumerate(productos_vendidos):
            id_producto = int(id_producto)
            if id_producto < 1 or id_producto > len(inventario):
                flash(f'El producto con ID {id_producto} no existe.', 'error')
                return redirect(url_for('vender_producto'))

            cantidad_vendida = int(cantidades_vendidas[index]) if cantidades_vendidas[index].isdigit() and cantidades_vendidas[index] else 1

            if cantidad_vendida <= 0:
                flash(f'La cantidad vendida para el producto {inventario[id_producto - 1]["Nombre"]} debe ser un número positivo.', 'error')
                return redirect(url_for('vender_producto'))

            cantidad_actual = int(inventario[id_producto - 1]['Cantidad'])
            if cantidad_vendida > cantidad_actual:
                flash(f'No hay suficiente cantidad en el inventario para {inventario[id_producto - 1]["Nombre"]}.', 'error')
                return redirect(url_for('vender_producto'))

            actualizaciones[id_producto] = cantidad_actual - cantidad_vendida

            try:
                with open(VENTAS_PATH, mode='a', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow([  # Asegúrate de que los nombres de las columnas sean correctos
                        id_producto,
                        inventario[id_producto - 1]['Nombre'],
                        cantidad_vendida,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        float(inventario[id_producto - 1]['Precio'])  # Agregar el precio aquí
                    ])
                # Agregar la venta a las ventas del día
                ventas_del_dia.append({
                    'ID': id_producto,
                    'Nombre': inventario[id_producto - 1]['Nombre'],
                    'Cantidad Vendida': cantidad_vendida,
                    'Fecha': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'Precio': float(inventario[id_producto - 1]['Precio'])
                })
            except Exception as e:
                flash(f'Error al registrar la venta: {e}', 'error')
                return redirect(url_for('vender_producto'))

        for id_producto, nueva_cantidad in actualizaciones.items():
            inventario[id_producto - 1]['Cantidad'] = str(nueva_cantidad)

        try:
            with open(INVENTARIO_PATH, mode='w', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=inventario[0].keys())
                writer.writeheader()
                writer.writerows(inventario)
            flash('Productos vendidos con éxito.', 'success')
        except Exception as e:
            flash(f'Error al actualizar el inventario: {e}', 'error')

        return redirect(url_for('home'))

    return render_template('vender_producto.html', inventario=inventario)

@app.route('/buscar_producto', methods=['GET'])
@login_required
def buscar_producto():
    busqueda = request.args.get('query', '')
    inventario = cargar_inventario()
    resultados = [producto for producto in inventario if busqueda.lower() in producto['Nombre'].lower()]
    return render_template('vender_producto.html', inventario=resultados)

@app.route('/reporte_ventas')
@login_required
def reporte_ventas():
    ventas = cargar_ventas()  # Cargar las ventas desde el archivo CSV
    return render_template('reporte_ventas.html', ventas=ventas)

@app.route('/abrir_caja', methods=['POST'])
@login_required
def abrir_caja():
    global ventas_del_dia, fecha_apertura
    ventas_del_dia = []  # Reiniciar el registro de ventas
    fecha_apertura = datetime.now()  # Guardar la fecha de apertura
    flash('Caja abierta exitosamente.', 'success')
    return redirect(url_for('pagina_principal'))

@app.route('/cerrar_caja', methods=['POST'])
@login_required
def cerrar_caja():
    global ventas_del_dia, fecha_apertura
    resumen_ventas = generar_resumen_ventas(ventas_del_dia)

    # Generar PDF
    crear_pdf_resumen(resumen_ventas)

    # Reiniciar datos
    ventas_del_dia = []
    fecha_apertura = None

    return render_template('resumen_ventas.html', resumen=resumen_ventas)

def generar_resumen_ventas(ventas):
    resumen = {}
    for venta in ventas:
        fecha = venta['Fecha'].split()[0]  # Solo la fecha
        if fecha not in resumen:
            resumen[fecha] = {'total_ventas': 0, 'cantidad_total': 0}
        
        cantidad_vendida = int(venta['Cantidad Vendida'])
        precio_vendido = float(venta['Precio'])
        resumen[fecha]['total_ventas'] += cantidad_vendida * precio_vendido
        resumen[fecha]['cantidad_total'] += cantidad_vendida

    return resumen

def crear_pdf_resumen(resumen):
    filename = f'resumen_ventas_{fecha_apertura.strftime("%Y%m%d_%H%M")}.pdf'
    c = canvas.Canvas(filename, pagesize=letter)
    c.drawString(100, 750, "Resumen de Ventas")
    c.drawString(100, 730, f"Fecha: {fecha_apertura.strftime('%Y-%m-%d %H:%M')}")
    
    y = 700
    for fecha, datos in resumen.items():
        c.drawString(100, y, f"Fecha: {fecha} - Total Ventas: ${datos['total_ventas']:.2f}, Cantidad Total: {datos['cantidad_total']}")
        y -= 20
    
    c.save()

@app.route('/descargar_resumen/<filename>')
@login_required
def descargar_resumen(filename):
    return send_from_directory('.', filename, as_attachment=True)

# Rutas de gestión de clientes
@app.route('/clientes')
@login_required
def ver_clientes():
    clientes = cargar_clientes()
    return render_template('ver_clientes.html', clientes=clientes)

@app.route('/agregar_cliente', methods=['GET', 'POST'])
@login_required
def agregar_cliente():
    if request.method == 'POST':
        nombre = request.form['nombre']
        email = request.form['email']
        telefono = request.form['telefono']
        
        if not nombre or not email or not telefono:
            flash('Todos los campos son obligatorios', 'error')
            return redirect(url_for('agregar_cliente'))

        nuevo_id = len(cargar_clientes()) + 1
        try:
            with open(CLIENTES_PATH, mode='a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow([nuevo_id, nombre, email, telefono])
            flash('Cliente agregado exitosamente.', 'success')
            return redirect(url_for('ver_clientes'))
        except Exception as e:
            flash(f'Error al agregar el cliente: {e}', 'error')
            return redirect(url_for('agregar_cliente'))

    return render_template('agregar_cliente.html')

@app.route('/editar_cliente/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_cliente(id):
    clientes = cargar_clientes()
    if request.method == 'POST':
        nombre = request.form['nombre']
        email = request.form['email']
        telefono = request.form['telefono']
        
        if not nombre or not email or not telefono:
            flash('Todos los campos son obligatorios', 'error')
            return redirect(url_for('editar_cliente', id=id))

        if 0 < id <= len(clientes):
            clientes[id - 1] = {
                'ID': id,
                'Nombre': nombre,
                'Email': email,
                'Telefono': telefono
            }
            try:
                with open(CLIENTES_PATH, mode='w', newline='') as file:
                    writer = csv.DictWriter(file, fieldnames=clientes[0].keys())
                    writer.writeheader()
                    writer.writerows(clientes)
                flash('Cliente editado exitosamente.', 'success')
            except Exception as e:
                flash(f'Error al editar el cliente: {e}', 'error')
        else:
            flash('ID de cliente no válido.', 'error')
        return redirect(url_for('ver_clientes'))

    cliente = clientes[id - 1] if 0 < id <= len(clientes) else None
    return render_template('editar_cliente.html', cliente=cliente)

@app.route('/eliminar_cliente/<int:id>')
@login_required
def eliminar_cliente(id):
    clientes = cargar_clientes()
    if 0 < id <= len(clientes):
        clientes.pop(id - 1)
        try:
            with open(CLIENTES_PATH, mode='w', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=clientes[0].keys())
                writer.writeheader()
                writer.writerows(clientes)
            flash('Cliente eliminado exitosamente.', 'success')
        except Exception as e:
            flash(f'Error al eliminar el cliente: {e}', 'error')
    else:
        flash('ID de cliente no válido.', 'error')
    return redirect(url_for('ver_clientes'))

@app.route('/proveedores', methods=['GET'])
@login_required
def ver_proveedores():
    proveedores = cargar_proveedores()  # Cargar datos de proveedores
    return render_template('ver_proveedores.html', proveedores=proveedores)

# Inicializando la aplicación
if __name__ == '__main__':
    app.run(debug=True)