#python3 -m app.algorithms.reset_db
import psycopg2
from app.models.config import CONFIG

def borrar_tablas():
    # Lista de tablas en el orden correcto para evitar errores de llaves foráneas
    # Basado en tu esquema de creacion_tablas.txt y Usuario_Semilla
    tablas = [
        "Usuario_Semilla",
        "Me_Gusta",
        "Cancion_Playlist",
        "Historial",
        "Playlist",
        "Cancion",
        "Usuario"
    ]

    try:
        # Conectamos usando tu CONFIG de config.py
        conn = psycopg2.connect(**CONFIG)
        cursor = conn.cursor()
        
        print(f"--- Iniciando limpieza de la base de datos: {CONFIG['database']} ---")
        
        for tabla in tablas:
            # Usamos CASCADE para asegurar que se borren dependencias
            query = f"DROP TABLE IF EXISTS {tabla} CASCADE;"
            cursor.execute(query)
            print(f"✅ Tabla {tabla} eliminada.")
        
        conn.commit()
        print("\n--- ¡Base de datos limpia! Ya puedes volver a correr tu script de creación. ---")
        
    except Exception as e:
        print(f"❌ Error al borrar las tablas: {e}")
    finally:
        if conn:
            cursor.close()
            conn.close()

if __name__ == "__main__":
    confirmacion = input("⚠️ ¿ESTÁS SEGURO? Esto borrará todos los usuarios y canciones (s/n): ")
    if confirmacion.lower() == 's':
        borrar_tablas()
    else:
        print("Operación cancelada.")