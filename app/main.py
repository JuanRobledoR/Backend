import spotipy
import random
import asyncio
import numpy as np
from spotipy.oauth2 import SpotifyOAuth
import os
import httpx
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from app.routers import usuarios, interacciones, auth
from fastapi import Query

# Importaciones de servicios propios del proyecto
from app.services.spotify_service import SpotifyService
from app.services.audio_analysis import AudioAnalysisService  
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List, Optional, Union

# Importación del núcleo de la IA
from app.algorithms.algoritmo_genetico import RealGeneticOptimizer

# Routers para modularizar la app
from app.routers import usuarios, interacciones

from app.schemas import LikeRequest
from app.schemas import UsuarioCreate, UsuarioResponse, LikeRequest, CancionBase

from app.algorithms.algoritmo_genetico import RealGeneticOptimizer
from app.algorithms.pseudogenetico import GeneticOptimizer

from app.models.funciones_db import connection

from app.models.funciones_db import (
    crear_usuario_db, 
    obtener_usuario_por_id,
    contar_semillas_usuario,       # <--- Indispensable
    guardar_cancion_con_cromosoma, # <--- Indispensable
    registrar_semilla_db,          # <--- Indispensable
    registrar_like_db,             # <--- Indispensable
    crear_playlist_db,             # Para Spotify
    agregar_cancion_a_playlist_db  # Para Spotify
)




# Cargar .env]
load_dotenv()

# --- CONFIGURACIÓN DE LA APP ---
app = FastAPI(
    title="BeatMatch API",
    description="Backend para descubrimiento de música usando IA y Algoritmos Genéticos",
    version="1.0.0"
)

# Configuración CORS para que el Frontend(React) hable con este Backend
origins = ["*"] # ----CAMBIAR POR LA URL DEL FRONTEND-----

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- ROUTERS ---
# RUtas
app.include_router(usuarios.router)
app.include_router(interacciones.router)
app.include_router(auth.router)




# ---------------------------------------------------- #
# ------- MODELOS PYDANTIC (Esquemas de Datos) ------- #
# ---------------------------------------------------- #

# Modelo de procesamiento de la canción
class TrackCandidate(BaseModel):
    id: Union[str, int]
    titulo: str
    preview_url: str
    artista: str 
    imagen: str  

# Controlador del scroll infinito
class FeedRequest(BaseModel):
    playlist_id: str
    limit: int = 20
    seen_ids: List[Union[str, int]] = [] # Lista negra temporal para no repetir canciones en la sesión

# Genera una playlist (con el algoritmo genético)basada en canciones objetivo
class PlaylistRequest(BaseModel):
    target_track_url: str       
    candidates: List[TrackCandidate]

# Guarda la playlist en la cuenta de spoti vinculada del usuario
#----- NO FUNCIONA AUN -----
class SavePlaylistRequest(BaseModel):
    track_ids: List[str] 
    name: str = "BeatMatch Discovery"
    description: str = "Playlist generada con BeatMatch App"

# Solicitud para crear una playlist automatica con algoritmo genetico 
class SmartPlaylistRequest(BaseModel):
    id_usuario: int
    nombre_playlist: str = "Playlist IA Generada"
    semilla_id: Optional[str] = None # Si es null, se hacen pseudomegustas

#Importa una playlist de spotify a la BD
class ImportSpotifyRequest(BaseModel):
    id_usuario: int
    spotify_playlist_id: str

# Rellena una playlist existente con recomendaciones IA (de algoritmo genetico)
class CompletePlaylistRequest(BaseModel):
    id_usuario: int
    id_playlist: int





# ------------------------------------------------------------------------------------------------------------------------------
# ------- ENDPOINTS GENERALES Y SPOTIFY ----------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------------------

# Endpoint base
@app.get("/")
def inicio():
    return "BeatMatch funcionando"

# Obtiene las canciones de una playlist de spotify 
@app.get("/playlist-tracks/{PLAYLIST_ID}")
def top_tracks(PLAYLIST_ID: str):
    spotify_service = SpotifyService()
    resultado = spotify_service.enlistar_playlist(PLAYLIST_ID)
    return resultado

#Obtiene metadatos detallados de una canción de spotify
@app.get("/datos-cancion/{TRACK_ID}")
def datos_cancion(TRACK_ID: str):
    spotify_service = SpotifyService()
    resultado = spotify_service.leer_datos_cancion(TRACK_ID)
    return resultado

# Exporta las canciones seleccionadas a la cuenta de spoti
@app.post("/crear-playlist-spotify")
def crear_playlist_usuario(payload: SavePlaylistRequest):
    try:
        sp_service = SpotifyService()
        
        # 1. Crea la playlist vacía en Spotify
        user_id = sp_service.sp.current_user()['id']
        playlist = sp_service.sp.user_playlist_create(
            user=user_id, 
            name=payload.name, 
            public=False, 
            description=payload.description
        )
        
        # 2. Formatea IDs a URIs de Spotify
        track_uris = [f"spotify:track:{tid}" if "spotify:track:" not in tid else tid for tid in payload.track_ids]
        
        # 3. Subie canciones en lotes de 100 (Batching)
        for i in range(0, len(track_uris), 100):
            batch = track_uris[i:i+100]
            sp_service.sp.playlist_add_items(playlist_id=playlist['id'], items=batch)
            
        return {
            "status": "success", 
            "playlist_url": playlist['external_urls']['spotify'], 
            "msg": "Playlist guardada correctamente"
        }
    
    except Exception as e:
        print(f"Error guardando playlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/importar-playlist-spotify")
async def importar_spotify(payload: ImportSpotifyRequest):
    """
    IMPORTACIÓN INTELIGENTE Y POBLADO DE DB:
    1. Trae tracks de Spotify.
    2. Crea la playlist en Postgres.
    3. Para cada track:
       - Busca en Deezer para obtener el MP3 (Preview).
       - Si no tiene cromosoma en la DB, lo genera con la IA.
       - Guarda todo en la DB global (Pool de canciones).
       - Si el usuario necesita semillas de onboarding, las registra.
    """
    try:
        sp = SpotifyService()
        analyzer = AudioAnalysisService()
        
        # Importaciones locales para evitar líos de dependencias
        from app.models.funciones_db import (
            crear_playlist_db, 
            guardar_cancion_con_cromosoma, 
            agregar_cancion_a_playlist_db,
            contar_semillas_usuario,
            registrar_semilla_db,
            crear_usuario_db, 
            obtener_usuario_por_id,
            contar_semillas_usuario,       # <--- IMPORTANTE
            guardar_cancion_con_cromosoma, # <--- IMPORTANTE
            registrar_semilla_db,          # <--- IMPORTANTE
            registrar_like_db
        )

        print(f"--- 1. Obteniendo tracks de Spotify: {payload.spotify_playlist_id} ---")
        tracks_spotify = sp.enlistar_playlist(payload.spotify_playlist_id)
        
        if not tracks_spotify:
            raise HTTPException(status_code=404, detail="No se encontraron canciones en Spotify")

        # Crear playlist en DB
        nombre_pl = f"Importada de Spotify ({len(tracks_spotify)} canciones)"
        id_playlist_nueva = crear_playlist_db(payload.id_usuario, nombre_pl)

        count_procesadas = 0
        
        # Revisamos cuántas semillas le faltan al usuario para el onboarding
        semillas_actuales = contar_semillas_usuario(payload.id_usuario)

        print(f"--- 2. Procesando y Analizando ({len(tracks_spotify)} canciones) ---")
        
        async with httpx.AsyncClient() as client:
            for t in tracks_spotify:
                titulo = t['name']
                artista = t['artists'][0]['name'] if t['artists'] else "Unknown"
                id_spotify = t['id']
                
                datos_cancion = {
                    "id_externo": id_spotify,
                    "plataforma": "SPOTIFY",
                    "titulo": titulo,
                    "artista": artista,
                    "imagen_url": "", 
                    "preview_url": "" 
                }

                # --- A. Búsqueda de Preview en Deezer ---
                cromosoma = None
                try:
                    q = f'artist:"{artista}" track:"{titulo}"'
                    resp = await client.get("https://api.deezer.com/search", params={"q": q, "limit": 1})
                    data = resp.json()
                    
                    if data.get('data'):
                        match = data['data'][0]
                        datos_cancion['imagen_url'] = match['album']['cover_xl']
                        datos_cancion['preview_url'] = match['preview']
                        
                        # --- B. Análisis de Audio (Solo si tenemos preview) ---
                        if datos_cancion['preview_url']:
                            print(f"🧬 Analizando vibe de: {titulo}")
                            cromo_raw = analyzer.generar_cromosoma(datos_cancion['preview_url'])
                            if cromo_raw is not None:
                                cromosoma = cromo_raw.tolist()
                    else:
                        print(f"⚠️ Sin preview para: {titulo}")

                except Exception as e:
                    print(f"Error en cruce/análisis de {titulo}: {e}")

                # --- C. Guardado en el Pool Global (Tabla Cancion) ---
                # Esta función hace el insert/update con el cromosoma
                id_cancion_db = guardar_cancion_con_cromosoma(datos_cancion, cromosoma)

                if id_cancion_db:
                    # --- D. Vincular a la Playlist del usuario ---
                    agregar_cancion_a_playlist_db(id_playlist_nueva, datos_cancion)
                    
                    # --- E. Lógica de Onboarding (Auto-completado) ---
                    # Si el usuario tiene menos de 10 semillas, usamos estas como sus semillas iniciales
                    if semillas_actuales < 10:
                        registrar_semilla_db(payload.id_usuario, id_cancion_db)
                        semillas_actuales += 1
                    
                    count_procesadas += 1

        return {
            "mensaje": "Importación y Análisis completado", 
            "playlist_id": id_playlist_nueva, 
            "nuevas_en_pool": count_procesadas,
            "onboarding_status": f"{semillas_actuales}/10 semillas"
        }

    except Exception as e:
        print(f"Error fatal importando: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))









# ------------------------------------------------------------------------------------------------------------------------------
# ------- UTILIDADES DEEZER Y ANÁLISIS -----------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------------------

# Convierte un MP3 en un cromosoma
@app.get("/features/") 
def get_features(url_cancion: str): 
    audio_analisis = AudioAnalysisService()
    print(f"Procesando URL: {url_cancion}") 
    resultado = audio_analisis.generar_cromosoma(url_cancion)
    
    if resultado is not None:
        return {"cromosoma": resultado.tolist()} 
    else:
        return {"error": "No se pudo procesar el audio"}

# Buscador simple
@app.get("/buscar")
async def buscar_cancion(q: str):
    if not q:
        return []
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.deezer.com/search?q={q}&limit=5")
        data = response.json()
        
    resultados = []
    if "data" in data:
        for track in data["data"]:
            resultados.append({
                "id": track["id"],
                "titulo": track["title"],
                "artista": track["artist"]["name"],
                "imagen": track["album"]["cover_xl"],
                "preview": track["preview"]
            })
    return resultados

# Obtiene la URL de preview de spotify en caso de que exista
@app.get("/preview/{TRACK_ID}")
def preview(TRACK_ID: str):
    spotify_service = SpotifyService()
    resultado = spotify_service.obtener_url_preview(TRACK_ID)
    return resultado








# ------------------------------------------------------------------------------------------------------------------------------
# ------- SISTEMA DE DESCUBRIMIENTO (FEED INFINITO) ----------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------------------

#Genera lotes de canciones para la interfaz swipe tipo tinder y usa una playlist como semilla para buscar recomendaciones
@app.post("/feed-playlist")
async def feed_playlist_infinito(payload: FeedRequest):
    try:
        print(f"Generando lote de {payload.limit} canciones. Excluyendo {len(payload.seen_ids)} ya vistas.")
        
        spotify_service = SpotifyService()
        
        # 1. Obtiene canciones base para inspirarse
        tracks_origen = spotify_service.enlistar_playlist(payload.playlist_id)
        if not tracks_origen:
            return {"error": "Playlist vacía"}

        # 2. Blacklist de canciones ya vistas
        blacklist_ids = set()
        for sid in payload.seen_ids:
            blacklist_ids.add(str(sid))
            
        resultados_finales = []
        conteo_artistas_lote = {} # Para evitar que un solo artista inunde el feed
        intentos_totales = 0
        MAX_INTENTOS = 15 
        
        async with httpx.AsyncClient(timeout=25.0) as client:
            
            # Bucle de búsqueda hasta llenar el límite o rendirse
            while len(resultados_finales) < payload.limit and intentos_totales < MAX_INTENTOS:
                
                # A. Elegir una canción semilla al azar
                semilla_sp = random.choice(tracks_origen)
                nombre_semilla = semilla_sp.get('name', '')
                try:
                    artista_semilla = semilla_sp['artists'][0]['name']
                except:
                    artista_semilla = ""
                
                # B. Buscar esa semilla en Deezer para obtener su ID de Artista/Track
                query = f'{artista_semilla} {nombre_semilla}'
                search_res = await client.get("https://api.deezer.com/search", params={"q": query, "limit": 1})
                search_data = search_res.json()
                
                if not search_data.get('data'):
                    intentos_totales += 1
                    continue 
                
                deezer_track = search_data['data'][0]
                deezer_id = deezer_track['id']
                deezer_artist_id = deezer_track['artist']['id']

                # C. Obtener candidatos (Estrategia mixta: Related Tracks o Top Artist)
                candidatos_raw = []
                
                # Intento 1: API Related (Canciones similares)
                rel_res = await client.get(f"https://api.deezer.com/track/{deezer_id}/related")
                rel_data = rel_res.json()
                
                if 'data' in rel_data and len(rel_data['data']) > 0:
                    candidatos_raw = rel_data['data']
                else:
                    # Intento 2 (Fallback): Top canciones del mismo artista
                    top_res = await client.get(f"https://api.deezer.com/artist/{deezer_artist_id}/top?limit=30")
                    top_data = top_res.json()
                    if 'data' in top_data:
                        candidatos_raw = top_data['data']

                # D. Filtrado y Selección
                random.shuffle(candidatos_raw)
                
                for track in candidatos_raw:
                    if len(resultados_finales) >= payload.limit:
                        break
                        
                    t_id = str(track['id'])
                    t_artist = track['artist']['name']
                    
                    # Filtros de calidad
                    if t_id in blacklist_ids: continue # Ya vista
                    if any(r['id'] == track['id'] for r in resultados_finales): continue # Duplicada en este lote
                    
                    # Filtro de variedad: Máximo 2 canciones del mismo artista por lote
                    count = conteo_artistas_lote.get(t_artist, 0)
                    if count >= 2: continue 
                    
                    resultados_finales.append({
                        "id": track["id"],
                        "titulo": track["title"],
                        "artista": t_artist,
                        "imagen": track["album"]["cover_xl"],
                        "preview": track["preview"],
                    })
                    
                    blacklist_ids.add(t_id)
                    conteo_artistas_lote[t_artist] = count + 1
                
                intentos_totales += 1

        print(f"Lote completado: {len(resultados_finales)} canciones.")
        return resultados_finales

    except Exception as e:
        print(f"ERROR FATAL EN FEED: {str(e)}")
        import traceback
        traceback.print_exc()
        return []
    







# ------------------------------------------------------------------------------------------------------------------------------
# ------- ALGORITMO GENÉTICO (IA) ----------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------------------

# Endpoint base para ejecutar el algoritmo genetico
# Recibe una o varias canciones objetivo y una lista de candidatos, devuelve la mejor combinación
@app.post("/generar-playlist-inteligente")
async def generar_playlist_inteligente(payload: PlaylistRequest):
    analyzer = AudioAnalysisService()
    
    print("--- 1. Analizando Target ---")
    target_cromosoma = analyzer.generar_cromosoma(payload.target_track_url)
    if target_cromosoma is None:
        return {"error": "No se pudo analizar la canción objetivo"}

    print(f"--- 2. Analizando {len(payload.candidates)} Candidatos ---")
    processed_candidates = [] # <--- Esta es la lista correcta
    
    for track in payload.candidates:
        if track.preview_url:
            try:
                cromo = analyzer.generar_cromosoma(track.preview_url)
                if cromo is not None:
                    processed_candidates.append({
                        "id": track.id,
                        "titulo": track.titulo,
                        "preview": track.preview_url,
                        "artista": track.artista, 
                        "imagen": track.imagen,
                        "cromosoma": cromo.tolist()
                    })
            except Exception as e:
                print(f"Error analizando {track.titulo}: {e}")
                
    if len(processed_candidates) < 5:
        return {"error": "No hay suficientes candidatos válidos."}

    # --- 3. Evolución Genética ---
    # Cambiamos 'candidatos_analizados' por 'processed_candidates'
    optimizer = RealGeneticOptimizer(song_pool=processed_candidates, target_vibe=target_cromosoma)
    
    mejor_playlist = optimizer.run()
    
    # Limpiar resultado
    resultado_limpio = []
    for track in mejor_playlist:
        track_copy = track.copy()
        if 'cromosoma' in track_copy:
            del track_copy['cromosoma']
        resultado_limpio.append(track_copy)

    return {"playlist_generada": resultado_limpio}


# FLUJO COMPLETO AUTOMÁTICO:
    # 1. Crea playlist vacía en BD.
    # 2. Determina el 'Vibe' (objetivo) basado en likes del usuario.
    # 3. Busca candidatos en internet (Deezer).
    # 4. Selecciona los mejores con IA.
    # 5. Guarda todo en DB.
@app.post("/crear-playlist-inteligente-auto")
async def auto_smart_playlist(payload: SmartPlaylistRequest):

    # Importaciones locales
    from app.models.funciones_db import crear_playlist_db, agregar_cancion_a_playlist_db, obtener_likes_db
    
    id_nueva_playlist = crear_playlist_db(payload.id_usuario, payload.nombre_playlist)
    
    analyzer = AudioAnalysisService()
    target_cromosoma = None
    
    # --- Definir el Objetivo (Target) ---
    likes = obtener_likes_db(payload.id_usuario)
    if not payload.semilla_id and likes:
        # Si no hay semilla explícita, usamos el último me gusta
        last_like = likes[0]
        print(f"Usando semilla de Like: {last_like['titulo']}")
        target_cromosoma = analyzer.generar_cromosoma(last_like['preview'])
        query_artist = last_like['artista']
    else:
        # Fallback de seguridad xdd
        query_artist = "Daft Punk" 

    if target_cromosoma is None:
        # Vector aleatorio si falla el análisis
        import numpy as np
        target_cromosoma = np.random.rand(16)

    # --- Búsqueda de Población (Candidatos) ---
    candidatos_analizados = []
    
    async with httpx.AsyncClient() as client:
        # Traemos 50 canciones relacionadas
        resp = await client.get(f"https://api.deezer.com/search?q=artist:'{query_artist}'&limit=50")
        data = resp.json()
        
        candidates_raw = data.get('data', [])
        
        # Analizamos su audio (Cuello de botella: procesar audio toma tiempo)
        print("Analizando audios para la IA...")
        for track in candidates_raw[:30]: 
            if track['preview']:
                cromo = analyzer.generar_cromosoma(track['preview'])
                if cromo is not None:
                    candidatos_analizados.append({
                        "id": track["id"],
                        "id_externo": str(track["id"]),
                        "titulo": track["title"],
                        "artista": track["artist"]["name"],
                        "imagen_url": track["album"]["cover_xl"],
                        "preview_url": track["preview"],
                        "cromosoma": cromo.tolist(),
                        "plataforma": "DEEZER"
                    })

    # --- Selección Natural ---
    if len(candidatos_analizados) > 5:
        print("Ejecutando Evolución...")
        optimizer = GeneticOptimizer(
            population_data=candidatos_analizados, 
            target_chromosome=target_cromosoma.tolist() if isinstance(target_cromosoma, np.ndarray) else target_cromosoma,
            target_size=20
        )
        seleccion_ia = optimizer.run()
    else:
        seleccion_ia = candidatos_analizados

    # --- Guardado ---
    for track in seleccion_ia:
        agregar_cancion_a_playlist_db(id_nueva_playlist, track)

    return {"mensaje": "Playlist Generada con Éxito", "total": len(seleccion_ia)}




# Rellena huecos en una playlist existente
# Tiene lógica de respaldo(Fallback) robusta para encontrar el estilo musical e incluso si las canciones originales no tienen audio preview
@app.post("/completar-playlist-ia")
async def completar_playlist_existente(payload: CompletePlaylistRequest):
    from app.models.funciones_db import obtener_canciones_playlist_db, agregar_cancion_a_playlist_db, obtener_likes_db
    import numpy as np
    
    analyzer = AudioAnalysisService()
    
    # 1. Obtener canciones actuales de la playlist
    canciones_actuales = obtener_canciones_playlist_db(payload.id_playlist)
    
    target_cromosoma = None
    query_artist = "Daft Punk" 
    
    # --- ESTRATEGIA A: Promedio de audio existente ---
    # Busca canciones que SÍ tengan preview (MP3)
    validas = [c for c in canciones_actuales if c['preview'] and len(c['preview']) > 0]
    
    if validas:
        print(f"Analizando {len(validas)} canciones con audio nativo...")
        cromosomas = []
        for c in validas[:5]: 
            try:
                cromo = analyzer.generar_cromosoma(c['preview'])
                if cromo is not None:
                    cromosomas.append(cromo)
            except: pass
        
        # El objetivo es el PROMEDIO matemático de las canciones actuales
        if cromosomas:
            target_cromosoma = np.mean(cromosomas, axis=0)
            query_artist = validas[0]['artista']


    # --- ESTRATEGIA B: Referencia Externa (Para playlists de Spotify) ---
    # Si las canciones existen pero no tienen MP3 (importadas de Spotify), 
    # buscamos la primera canción en Deezer para obtener su audio.
    if target_cromosoma is None and len(canciones_actuales) > 0:
        print("⚠️ Playlist sin audio nativo. Buscando referencia externa...")
        ref_track = canciones_actuales[0]
        query_artist = ref_track['artista']
        
        async with httpx.AsyncClient() as client:
            try:
                q = f"{query_artist} {ref_track['titulo']}"
                resp = await client.get(f"https://api.deezer.com/search?q={q}&limit=1")
                data = resp.json()
                if data.get('data'):
                    deezer_match = data['data'][0]
                    if deezer_match.get('preview'):
                        print(f"✅ Referencia encontrada: {deezer_match['title']}")
                        target_cromosoma = analyzer.generar_cromosoma(deezer_match['preview'])
            except Exception as e:
                print(f"Error buscando referencia: {e}")

    # --- ESTRATEGIA C: Historial de usuario ---
    # Si la playlist está vacía, nos basamos en sus Likes.
    if target_cromosoma is None:
        print("Playlist vacía. Usando 'Me Gusta'...")
        likes = obtener_likes_db(payload.id_usuario)
        if likes:
            last = likes[0]
            if last.get('preview'): 
                target_cromosoma = analyzer.generar_cromosoma(last['preview'])
                query_artist = last['artista']
    
    if target_cromosoma is None:
        raise HTTPException(status_code=400, detail="Imposible determinar el estilo musical (sin audio/likes).")

    # 3. Buscar nuevos candidatos en Deezer
    candidatos_analizados = []
    ids_existentes = set(str(c['id_externo']) for c in canciones_actuales)

    async with httpx.AsyncClient() as client:
        print(f"Buscando candidatos similares a: {query_artist}")
        resp = await client.get(f"https://api.deezer.com/search?q=artist:'{query_artist}'&limit=50")
        data = resp.json()
        raw = data.get('data', [])
        
        for track in raw:
            # Evitar agregar canciones que ya están en la playlist
            if str(track['id']) in ids_existentes: continue 
            
            if track['preview']:
                try:
                    cromo = analyzer.generar_cromosoma(track['preview'])
                    if cromo is not None:
                        candidatos_analizados.append({
                            "id": track["id"], 
                            "id_externo": str(track["id"]), 
                            "titulo": track["title"],
                            "artista": track["artist"]["name"],
                            "imagen_url": track["album"]["cover_xl"],
                            "preview_url": track["preview"],
                            "cromosoma": cromo.tolist(),
                            "plataforma": "DEEZER"
                        })
                except: pass
                
                # Limitamos a 15 candidatos analizados por velocidad
                if len(candidatos_analizados) >= 15: break 

    # 4. Optimización con Algoritmo Genético
    if not candidatos_analizados:
         return {"mensaje": "No se encontraron candidatos suficientes."}

    optimizer = GeneticOptimizer(
        population_data=candidatos_analizados, 
        target_chromosome=target_cromosoma.tolist(),
        target_size=5 # Solo queremos agregar 5 canciones nuevas
    )
    seleccion = optimizer.run()

    # 5. Guardar en Base de Datos
    count = 0
    for track in seleccion:
        track_db = track.copy()
        if agregar_cancion_a_playlist_db(payload.id_playlist, track_db):
            count += 1

    return {"mensaje": "Completado con éxito", "agregadas": count}


# Nuevo endpoint para el Onboarding
@app.get("/usuarios/check-onboarding/{id_usuario}")
def check_onboarding(id_usuario: int):
    count = contar_semillas_usuario(id_usuario) 
    return {
        "completado": count >= 10,
        "faltantes": max(0, 10 - count)
    }

@app.post("/usuarios/registrar-semilla")
async def registrar_semilla(payload: LikeRequest):
    analyzer = AudioAnalysisService()
    
    # Análisis de audio
    cromosoma = None
    if payload.cancion.preview_url:
        cromo_raw = analyzer.generar_cromosoma(payload.cancion.preview_url)
        if cromo_raw is not None:
            cromosoma = cromo_raw.tolist()

    # Guardado en Pool Global (Tabla Cancion)
    id_cancion = guardar_cancion_con_cromosoma(payload.cancion.dict(), cromosoma)
    
    if id_cancion:
        # Registrar en la tabla de control de onboarding
        registrar_semilla_db(payload.id_usuario, id_cancion)
        
        # Guardar directamente en la tabla de "Me Gusta"
        registrar_like_db(payload.id_usuario, payload.cancion.dict())
        
        return {
            "mensaje": "Semilla y Like registrados", 
            "total": contar_semillas_usuario(payload.id_usuario)
        }
    
    raise HTTPException(status_code=500, detail="Error al procesar la canción en la BD")





async def refrescar_links_deezer(lista_canciones: list):
    import httpx
    import asyncio
    async with httpx.AsyncClient(timeout=10.0) as client:
        tareas = []
        for s in lista_canciones:
            id_deezer = s.get('id_externo')
            url_api = f"https://api.deezer.com/track/{id_deezer}"
            tareas.append(client.get(url_api))
        
        respuestas = await asyncio.gather(*tareas, return_exceptions=True)
        for i, resp in enumerate(respuestas):
            if isinstance(resp, httpx.Response) and resp.status_code == 200:
                lista_canciones[i]['preview'] = resp.json().get('preview')
    return lista_canciones

# 2. Endpoint de la IA con Exclusión en tiempo real
@app.get("/generar-smart-playlist/{id_usuario}")
async def endpoint_ia_real(id_usuario: int, exclude: List[int] = Query([])):
    from app.models.funciones_db import connection
    import numpy as np
    cursor = connection.cursor()

    try:
        # A. Obtener historial y likes de la DB + lo que el front ya tiene
        cursor.execute("SELECT id_cancion FROM Historial WHERE id_usuario = %s UNION SELECT id_cancion FROM Me_Gusta WHERE id_usuario = %s", (id_usuario, id_usuario))
        vistas_db = [r[0] for r in cursor.fetchall()]
        
        # Lista negra total: DB + lo que el usuario está viendo actualmente
        lista_negra = list(set(vistas_db + exclude))

        # B. ADN del usuario (Promedio de sus Likes)
        cursor.execute("SELECT c.cromosoma FROM Me_Gusta m JOIN Cancion c ON m.id_cancion = c.id_cancion WHERE m.id_usuario = %s AND c.cromosoma IS NOT NULL ORDER BY m.fecha_like DESC LIMIT 20", (id_usuario,))
        semillas = cursor.fetchall()
        if not semillas:
            raise HTTPException(status_code=400, detail="Faltan likes")

        target_vibe = np.mean([np.array(s[0]) for s in semillas], axis=0)

        # C. Obtener candidatos EXCLUYENDO la lista negra
        query = "SELECT id_cancion, titulo, artista, imagen_url, preview_url, cromosoma, id_externo FROM Cancion WHERE cromosoma IS NOT NULL"
        if lista_negra:
            query += f" AND id_cancion NOT IN ({','.join(map(str, lista_negra))})"
        
        cursor.execute(query + " LIMIT 300")
        rows = cursor.fetchall()
        
        # Fix NameError: Definir song_pool siempre
        song_pool = [{"id": r[0], "titulo": r[1], "artista": r[2], "imagen": r[3], "preview": r[4], "cromosoma": r[5], "id_externo": r[6]} for r in rows]

        if len(song_pool) < 5:
             # Si se acaban, relajamos el filtro pero mezclamos para que no se sienta igual
             cursor.execute("SELECT id_cancion, titulo, artista, imagen_url, preview_url, cromosoma, id_externo FROM Cancion WHERE cromosoma IS NOT NULL ORDER BY RANDOM() LIMIT 100")
             rows = cursor.fetchall()
             song_pool = [{"id": r[0], "titulo": r[1], "artista": r[2], "imagen": r[3], "preview": r[4], "cromosoma": r[5], "id_externo": r[6]} for r in rows]

        # D. IA y Limpieza
        optimizer = RealGeneticOptimizer(song_pool, target_vibe, playlist_size=10)
        mejor_playlist = optimizer.run()
        
        resultado = []
        for s in mejor_playlist:
            t = s.copy()
            t.pop('cromosoma', None)
            resultado.append(t)

        # E. REFRESH DE AUDIO (Para que funcionen las previews)
        return {"playlist_evolucionada": await refrescar_links_deezer(resultado)}

    finally:
        cursor.close()



@app.post("/usuarios/registrar-semilla")
async def registrar_semilla(payload: LikeRequest):
    analyzer = AudioAnalysisService()
    from app.models.funciones_db import (
        guardar_cancion_con_cromosoma, 
        registrar_semilla_db, 
        registrar_like_db,
        contar_semillas_usuario
    )
    
    # 1. Analizar y Guardar en Pool Global
    cromosoma = None
    if payload.cancion.preview_url:
        cromo_raw = analyzer.generar_cromosoma(payload.cancion.preview_url)
        if cromo_raw is not None:
            cromosoma = cromo_raw.tolist()

    id_cancion = guardar_cancion_con_cromosoma(payload.cancion.dict(), cromosoma)
    
    if id_cancion:
        # 2. Registrar como Semilla (para el control de onboarding)
        registrar_semilla_db(payload.id_usuario, id_cancion)
        
        # 3. ¡NUEVO!: Guardar directamente en "Me Gusta"
        registrar_like_db(payload.id_usuario, payload.cancion.dict())
        
        return {"mensaje": "Semilla y Like registrados", "total": contar_semillas_usuario(payload.id_usuario)}
    
    raise HTTPException(status_code=500, detail="Error al procesar")


@app.get("/admin/stats")
def get_admin_stats():
    from app.models.config import connection
    cursor = connection.cursor()
    
    # 1. Total de usuarios
    cursor.execute("SELECT COUNT(*) FROM Usuario")
    total_usuarios = cursor.fetchone()[0]
    
    # 2. Total de canciones en el pool global
    cursor.execute("SELECT COUNT(*) FROM Cancion")
    total_canciones = cursor.fetchone()[0]
    
    # 3. Canciones ya analizadas por la IA (con cromosoma)
    cursor.execute("SELECT COUNT(*) FROM Cancion WHERE cromosoma IS NOT NULL")
    canciones_ia = cursor.fetchone()[0]
    
    # 4. Últimas 5 canciones agregadas
    cursor.execute("SELECT titulo, artista, plataforma FROM Cancion ORDER BY id_cancion DESC LIMIT 5")
    recientes = [{"titulo": r[0], "artista": r[1], "plataforma": r[2]} for r in cursor.fetchall()]
    
    cursor.close()
    return {
        "usuarios": total_usuarios,
        "canciones_totales": total_canciones,
        "canciones_ia": canciones_ia,
        "recientes": recientes
    }