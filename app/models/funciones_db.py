import psycopg2
from app.models.config import connection
import json

# Inserta usuario en DB
def crear_usuario_db(datos_usuario: dict):
    try:
        cursor = connection.cursor()
        query = """
            INSERT INTO Usuario (
                nombre_usuario, apellido_paterno, apellido_materno, 
                email, usuario, contrasena, tipo_usuario, genero
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id_usuario, nombre_usuario, email;
        """
        valores = (
            datos_usuario['nombre_usuario'],
            datos_usuario['apellido_paterno'],
            datos_usuario['apellido_materno'],
            datos_usuario['email'],
            datos_usuario['usuario'],
            datos_usuario['contrasena'], 
            False, 
            datos_usuario['genero']
        )
        cursor.execute(query, valores)
        nuevo_usuario = cursor.fetchone()
        connection.commit()
        cursor.close()
        return nuevo_usuario
    except Exception as e:
        connection.rollback()
        print(f"Error crear usuario: {e}")
        return None

# Busca usuario por ID
def obtener_usuario_por_id(id_usuario: int):
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM Usuario WHERE id_usuario = %s", (id_usuario,))
        row = cursor.fetchone()
        cursor.close()
        if row:
            return {
                "id_usuario": row[0],
                "nombre_usuario": row[1],
                "apellido_paterno": row[2],
                "apellido_materno": row[3],
                "email": row[4],
                "usuario": row[5],
                "tipo_usuario": row[7],
                "genero": row[8]
            }
        return None
    except Exception as e:
        print(e)
        return None
    
# Upsert de canción y cromosoma
def guardar_cancion_con_cromosoma(datos_cancion: dict, cromosoma: list):
    try:
        cursor = connection.cursor()
        cromosoma_json = json.dumps(cromosoma) if cromosoma else None
        
        query = """
            INSERT INTO Cancion (id_externo, plataforma, titulo, artista, album, imagen_url, preview_url, cromosoma)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id_externo, plataforma) 
            DO UPDATE SET cromosoma = EXCLUDED.cromosoma
            RETURNING id_cancion;
        """
        cursor.execute(query, (
            str(datos_cancion['id_externo']),
            datos_cancion['plataforma'],
            datos_cancion['titulo'],
            datos_cancion['artista'],
            datos_cancion.get('album'),
            datos_cancion.get('imagen_url'),
            datos_cancion.get('preview_url'),
            cromosoma_json
        ))
        id_cancion = cursor.fetchone()[0]
        connection.commit()
        cursor.close()
        return id_cancion
    except Exception as e:
        connection.rollback()
        print(f"Error guardando canción con cromosoma: {e}")
        return None

# Guarda selección de onboarding
def registrar_semilla_db(id_usuario: int, id_cancion: int):
    try:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO Usuario_Semilla (id_usuario, id_cancion) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (id_usuario, id_cancion)
        )
        connection.commit()
        cursor.close()
        return True
    except:
        return False

# Retorna conteo de semillas
def contar_semillas_usuario(id_usuario: int):
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM Usuario_Semilla WHERE id_usuario = %s", (id_usuario,))
    count = cursor.fetchone()[0]
    cursor.close()
    return count

# Procesa transacción de like
def registrar_like_db(id_usuario: int, datos_cancion: dict):
    try:
        cursor = connection.cursor()
        
        cursor.execute(
            "SELECT id_cancion FROM Cancion WHERE id_externo = %s AND plataforma = %s",
            (datos_cancion['id_externo'], datos_cancion['plataforma'])
        )
        resultado = cursor.fetchone()

        if resultado:
            id_cancion = resultado[0]
        else:
            query_cancion = """
                INSERT INTO Cancion (id_externo, plataforma, titulo, artista, album, imagen_url, preview_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id_cancion;
            """
            cursor.execute(query_cancion, (
                datos_cancion['id_externo'],
                datos_cancion['plataforma'],
                datos_cancion['titulo'],
                datos_cancion['artista'],
                datos_cancion.get('album', ''),
                datos_cancion.get('imagen_url', ''),
                datos_cancion.get('preview_url', '')
            ))
            id_cancion = cursor.fetchone()[0]

        query_like = """
            INSERT INTO Me_Gusta (id_usuario, id_cancion)
            VALUES (%s, %s)
            ON CONFLICT (id_usuario, id_cancion) DO NOTHING;
        """
        cursor.execute(query_like, (id_usuario, id_cancion))
        
        connection.commit()
        cursor.close()
        return id_cancion

    except Exception as e:
        connection.rollback()
        print(f"Error registrando like: {e}")
        return None

# Registra interacción en historial
def registrar_historial_db(id_usuario, id_cancion, tipo):
    try:
        cursor = connection.cursor()
        query = """
            INSERT INTO Historial (id_usuario, id_cancion, tipo_interaccion)
            VALUES (%s, %s, %s);
        """
        cursor.execute(query, (id_usuario, id_cancion, tipo))
        connection.commit()
        cursor.close()
    except Exception as e:
        print(f"Error historial: {e}")
        connection.rollback()

# Obtiene historial reciente
def obtener_historial_db(id_usuario):
    try:
        cursor = connection.cursor()
        # Se agrega id_externo, plataforma y preview para el frontend
        query = """
            SELECT c.titulo, c.artista, c.imagen_url, h.tipo_interaccion, h.fecha_interaccion, 
                   c.id_externo, c.plataforma, c.preview_url, c.id_cancion
            FROM Historial h
            JOIN Cancion c ON h.id_cancion = c.id_cancion
            WHERE h.id_usuario = %s
            ORDER BY h.fecha_interaccion DESC LIMIT 50;
        """
        cursor.execute(query, (id_usuario,))
        res = cursor.fetchall()
        cursor.close()
        return [{
            "titulo": r[0], 
            "artista": r[1], 
            "imagen": r[2], 
            "tipo": r[3], 
            "fecha": r[4],
            "id_externo": r[5],   
            "plataforma": r[6],
            "preview": r[7],      
            "id_interno": r[8]
        } for r in res]
    except Exception as e:
        print(f"Error obteniendo historial: {e}")
        return []
    
# Verifica o crea canción sin like
def asegurar_cancion_existente(datos_cancion: dict):
    try:
        cursor = connection.cursor()
        
        cursor.execute(
            "SELECT id_cancion FROM Cancion WHERE id_externo = %s AND plataforma = %s",
            (datos_cancion['id_externo'], datos_cancion['plataforma'])
        )
        resultado = cursor.fetchone()

        if resultado:
            id_cancion = resultado[0]
        else:
            query_cancion = """
                INSERT INTO Cancion (id_externo, plataforma, titulo, artista, album, imagen_url, preview_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id_cancion;
            """
            cursor.execute(query_cancion, (
                datos_cancion['id_externo'],
                datos_cancion['plataforma'],
                datos_cancion['titulo'],
                datos_cancion['artista'],
                datos_cancion.get('album', ''),
                datos_cancion.get('imagen_url', ''),
                datos_cancion.get('preview_url', '')
            ))
            id_cancion = cursor.fetchone()[0]
            connection.commit()
            
        cursor.close()
        return id_cancion 
    except Exception as e:
        connection.rollback()
        print(f"Error asegurando cancion: {e}")
        return None

# Inserta nueva playlist
def crear_playlist_db(id_usuario, nombre):
    try:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO Playlist (nombre, id_usuario) VALUES (%s, %s) RETURNING id_playlist", (nombre, id_usuario))
        id_playlist = cursor.fetchone()[0]
        connection.commit()
        cursor.close()
        return id_playlist
    except Exception as e:
        connection.rollback()
        print(f"Error creando playlist: {e}")
        return None

# Lista playlists de usuario
def obtener_playlists_db(id_usuario):
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT id_playlist, nombre FROM Playlist WHERE id_usuario = %s", (id_usuario,))
        res = cursor.fetchall()
        cursor.close()
        return [{"id": r[0], "nombre": r[1]} for r in res]
    except Exception as e:
        print(f"Error obteniendo playlists: {e}")
        return []

# Elimina playlist por ID
def eliminar_playlist_db(id_playlist):
    try:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM Playlist WHERE id_playlist = %s", (id_playlist,))
        connection.commit()
        cursor.close()
        return True
    except Exception as e:
        connection.rollback()
        print(f"Error eliminando playlist: {e}")
        return False
    
# Obtiene lista de me gusta
def obtener_likes_db(id_usuario: int):
    try:
        cursor = connection.cursor()
        query = """
            SELECT c.id_cancion, c.titulo, c.artista, c.imagen_url, c.preview_url 
            FROM Me_Gusta m
            JOIN Cancion c ON m.id_cancion = c.id_cancion
            WHERE m.id_usuario = %s
            ORDER BY m.fecha_like DESC;
        """
        cursor.execute(query, (id_usuario,))
        resultados = cursor.fetchall()
        cursor.close()
        
        likes = []
        for r in resultados:
            likes.append({
                "id": r[0],
                "titulo": r[1],
                "artista": r[2],
                "imagen": r[3],
                "preview": r[4]
            })
        return likes
    except Exception as e:
        print(f"Error obteniendo likes: {e}")
        return []
    
# Busca ID interno de canción
def obtener_id_cancion_db(id_externo, plataforma):
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id_cancion FROM Cancion WHERE id_externo = %s AND plataforma = %s",
            (str(id_externo), plataforma)
        )
        res = cursor.fetchone()
        cursor.close()
        return res[0] if res else None
    except:
        return None

# Vincula canción a playlist
def agregar_cancion_a_playlist_db(id_playlist: int, datos_cancion: dict):
    try:
        cursor = connection.cursor()
        
        cursor.execute(
            "SELECT id_cancion FROM Cancion WHERE id_externo = %s AND plataforma = %s",
            (str(datos_cancion['id_externo']), datos_cancion['plataforma'])
        )
        resultado = cursor.fetchone()

        if resultado:
            id_cancion = resultado[0]
        else:
            query_cancion = """
                INSERT INTO Cancion (id_externo, plataforma, titulo, artista, album, imagen_url, preview_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id_cancion;
            """
            cursor.execute(query_cancion, (
                str(datos_cancion['id_externo']),
                datos_cancion['plataforma'],
                datos_cancion['titulo'],
                datos_cancion['artista'],
                datos_cancion.get('album', ''),
                datos_cancion.get('imagen_url', ''),
                datos_cancion.get('preview_url', '')
            ))
            id_cancion = cursor.fetchone()[0]

        query_link = """
            INSERT INTO Cancion_Playlist (id_playlist, id_cancion)
            VALUES (%s, %s)
            ON CONFLICT (id_playlist, id_cancion) DO NOTHING;
        """
        cursor.execute(query_link, (id_playlist, id_cancion))
        connection.commit()
        cursor.close()
        return True
    except Exception as e:
        connection.rollback()
        print(f"Error agregando a playlist: {e}")
        return False

# Obtiene tracks de playlist
def obtener_canciones_playlist_db(id_playlist: int):
    try:
        cursor = connection.cursor()
        query = """
            SELECT c.id_cancion, c.titulo, c.artista, c.imagen_url, c.preview_url, c.id_externo
            FROM Cancion_Playlist cp
            JOIN Cancion c ON cp.id_cancion = c.id_cancion
            WHERE cp.id_playlist = %s
            ORDER BY cp.fecha_agregada DESC;
        """
        cursor.execute(query, (id_playlist,))
        res = cursor.fetchall()
        cursor.close()
        return [{
            "id": r[0], "titulo": r[1], "artista": r[2], 
            "imagen": r[3], "preview": r[4], "id_externo": r[5]
        } for r in res]
    except Exception as e:
        print(f"Error obteniendo canciones de playlist: {e}")
        return []

# Desvincula canción de playlist
def eliminar_cancion_de_playlist_db(id_playlist: int, id_cancion: int):
    try:
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM Cancion_Playlist WHERE id_playlist = %s AND id_cancion = %s", 
            (id_playlist, id_cancion)
        )
        connection.commit()
        cursor.close()
        return True
    except Exception as e:
        connection.rollback()
        return False
    
# Elimina registro de like
def eliminar_like_db(id_usuario, id_cancion_db):
    try:
        cursor = connection.cursor()
        query = "DELETE FROM Me_Gusta WHERE id_usuario = %s AND id_cancion = %s"
        cursor.execute(query, (id_usuario, id_cancion_db))
        connection.commit()
        cursor.close()
        return True
    except Exception as e:
        connection.rollback()
        print(f"Error eliminando like: {e}")
        return False

# Valida login
def verificar_credenciales_db(username, password):
    try:
        cursor = connection.cursor()
        query = "SELECT id_usuario, usuario, email FROM Usuario WHERE usuario = %s AND contrasena = %s"
        cursor.execute(query, (username, password))
        usuario = cursor.fetchone()
        cursor.close()
        
        if usuario:
            return {
                "id_usuario": usuario[0],
                "username": usuario[1],
                "email": usuario[2]
            }
        return None
    except Exception as e:
        print(f"Error en login db: {e}")
        return None