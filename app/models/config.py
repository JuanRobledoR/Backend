import psycopg2
import os

# Render proporciona la URL de conexión a través de esta variable de entorno
DATABASE_URL = os.getenv('DATABASE_URL')

try:
    if DATABASE_URL:
        # Configuración para PRODUCCIÓN (Render)
        # La URL ya contiene host, puerto, usuario y contraseña
        connection = psycopg2.connect(DATABASE_URL)
    else:
        # Configuración para DESARROLLO (Tu PC Local)
        CONFIG = {
            'host': '127.0.0.1',
            'port': '5432',
            'user': 'postgres',
            'password': 'juanito123',
            'database': 'beatmatchprueba01'    
        }
        connection = psycopg2.connect(**CONFIG)
    
    print("Conexion exitosa")

except Exception as e:
    # Es vital imprimir el error para debuguear en los logs de Render
    print(f"Error de conexión: {e}")
    # Definimos connection como None para evitar errores de importación si falla
    connection = None