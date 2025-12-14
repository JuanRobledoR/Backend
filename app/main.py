import spotipy
import random
import asyncio
from spotipy.oauth2 import SpotifyOAuth
import os
import httpx
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from app.services.spotify_service import SpotifyService
from app.services.audio_analysis import AudioAnalysisService  
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List, Optional, Union 
from app.algorithms.algoritmo_genetico import GeneticOptimizer
from app.routers import usuarios 
from app.routers import usuarios, interacciones

# --- MODELOS Pydantic ---

class TrackCandidate(BaseModel):
    id: Union[str, int]
    titulo: str
    preview_url: str
    artista: str 
    imagen: str  

# Modelo para el Feed Infinito
class FeedRequest(BaseModel):
    playlist_id: str
    limit: int = 20
    seen_ids: List[Union[str, int]] = [] # IDs que el usuario YA vio (para no repetir)

class PlaylistRequest(BaseModel):
    target_track_url: str       
    candidates: List[TrackCandidate]

# Nuevo modelo para guardar la playlist final
class SavePlaylistRequest(BaseModel):
    track_ids: List[str] # IDs de las canciones que recibieron "Like"
    name: str = "BeatMatch Discovery"
    description: str = "Playlist generada con BeatMatch App"

class SmartPlaylistRequest(BaseModel):
    id_usuario: int
    nombre_playlist: str = "Playlist IA Generada"
    semilla_id: Optional[str] = None # Puede ser un track ID para basars

class ImportSpotifyRequest(BaseModel):
    id_usuario: int
    spotify_playlist_id: str

class CompletePlaylistRequest(BaseModel):
    id_usuario: int
    id_playlist: int

load_dotenv()

app = FastAPI()

# Configuración CORS permisiva para desarrollo
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- ROUTERS / ENDPOINTS ---
app.include_router(usuarios.router)
app.include_router(interacciones.router)



@app.get("/")
def inicio():
    return "Hola - BeatMatch Backend Activo 🚀"


# ------------------------------------------------------------------------------------------------------------------------------
# ------- ENDPOINTS SPOTIFY ----------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------------------

@app.get("/playlist-tracks/{PLAYLIST_ID}")
def top_tracks(PLAYLIST_ID: str):
    spotify_service = SpotifyService()
    resultado = spotify_service.enlistar_playlist(PLAYLIST_ID)
    return resultado

@app.get("/datos-cancion/{TRACK_ID}")
def datos_cancion(TRACK_ID: str):
    spotify_service = SpotifyService()
    resultado = spotify_service.leer_datos_cancion(TRACK_ID)
    return resultado

# Nuevo Endpoint para GUARDAR la playlist en la cuenta del usuario
@app.post("/crear-playlist-spotify")
def crear_playlist_usuario(payload: SavePlaylistRequest):
    """
    Recibe la lista de IDs (los Likes del usuario) y crea una playlist real en Spotify.
    """
    try:
        sp_service = SpotifyService()
        # Asumiendo que tu SpotifyService tiene un método para crear playlists.
        # Si no lo tiene, necesitarás agregarlo (te dejo la lógica aquí abajo comentada por si acaso).
        
        # Lógica simulada de creación (Revisa tu servicio):
        user_id = sp_service.sp.current_user()['id']
        playlist = sp_service.sp.user_playlist_create(user=user_id, name=payload.name, public=False, description=payload.description)
        
        # Spotify a veces requiere URIs en formato 'spotify:track:ID'
        track_uris = [f"spotify:track:{tid}" if "spotify:track:" not in tid else tid for tid in payload.track_ids]
        
        # Agregar canciones en lotes de 100 (límite de Spotify)
        for i in range(0, len(track_uris), 100):
            batch = track_uris[i:i+100]
            sp_service.sp.playlist_add_items(playlist_id=playlist['id'], items=batch)
            
        return {"status": "success", "playlist_url": playlist['external_urls']['spotify'], "msg": "Playlist guardada correctamente"}
    
    except Exception as e:
        print(f"Error guardando playlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/importar-playlist-spotify")
async def importar_spotify(payload: ImportSpotifyRequest):
    """
    Importación HÍBRIDA:
    1. Obtiene la lista de canciones de Spotify (Id, Título, Artista).
    2. Busca cada canción en Deezer para obtener la IMAGEN y el PREVIEW (MP3).
    3. Guarda la mezcla perfecta en la Base de Datos.
    """
    try:
        sp = SpotifyService()
        print(f"--- 1. Obteniendo tracks de Spotify: {payload.spotify_playlist_id} ---")
        tracks_spotify = sp.enlistar_playlist(payload.spotify_playlist_id)
        
        if not tracks_spotify:
            raise HTTPException(status_code=404, detail="No se encontraron canciones en Spotify")

        # Usamos nombre genérico porque el endpoint de tracks no devuelve el nombre de la playlist
        nombre_pl = f"Importada de Spotify ({len(tracks_spotify)} canciones)"
        
        # Importamos las funciones de DB necesarias
        from app.models.funciones_db import crear_playlist_db, agregar_cancion_a_playlist_db
        
        id_playlist_nueva = crear_playlist_db(payload.id_usuario, nombre_pl)

        count = 0
        print(f"--- 2. Enriqueciendo datos con Deezer ({len(tracks_spotify)} canciones) ---")
        
        async with httpx.AsyncClient() as client:
            for t in tracks_spotify:
                titulo = t['name']
                artista = t['artists'][0]['name'] if t['artists'] else ""
                
                # Datos base (Por si Deezer falla, guardamos al menos el texto)
                datos_cancion = {
                    "id_externo": t['id'], # Mantenemos el ID de Spotify como referencia
                    "plataforma": "SPOTIFY",
                    "titulo": titulo,
                    "artista": artista,
                    "imagen_url": "", 
                    "preview_url": "" 
                }

                # --- MAGIA: BUSCAR EN DEEZER ---
                try:
                    # Buscamos por Artista + Título para mayor precisión
                    q = f'artist:"{artista}" track:"{titulo}"'
                    resp = await client.get("https://api.deezer.com/search", params={"q": q, "limit": 1})
                    data = resp.json()
                    
                    if data.get('data'):
                        match = data['data'][0]
                        # ¡ROBAMOS LOS DATOS RICOS!
                        datos_cancion['imagen_url'] = match['album']['cover_xl']
                        datos_cancion['preview_url'] = match['preview']
                        print(f"✅ Encontrada en Deezer: {titulo}")
                    else:
                        print(f"⚠️ No encontrada en Deezer (Se guarda sin audio): {titulo}")

                except Exception as e:
                    print(f"Error buscando en Deezer: {e}")

                # Guardamos en la DB
                if agregar_cancion_a_playlist_db(id_playlist_nueva, datos_cancion):
                    count += 1
        
        return {
            "mensaje": "Importación Inteligente exitosa", 
            "playlist_id": id_playlist_nueva, 
            "canciones_procesadas": count
        }

    except Exception as e:
        print(f"Error importando: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ------------------------------------------------------------------------------------------------------------------------------
# ------- ENDPOINTS DEEZER & FEATURES ------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------------------

@app.get("/features/") 
def get_features(url_cancion: str): 
    audio_analisis = AudioAnalysisService()
    print(f"Procesando URL: {url_cancion}") 
    resultado = audio_analisis.generar_cromosoma(url_cancion)
    
    if resultado is not None:
        return {"cromosoma": resultado.tolist()} 
    else:
        return {"error": "No se pudo procesar el audio"}
    
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

@app.get("/preview/{TRACK_ID}")
def preview(TRACK_ID: str):
    spotify_service = SpotifyService()
    resultado = spotify_service.obtener_url_preview(TRACK_ID)
    return resultado


# ------------------------------------------------------------------------------------------------------------------------------
# ------- NUEVO SISTEMA DE DESCUBRIMIENTO (Deezer Powered) ---------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------------------

@app.post("/feed-playlist")
async def feed_playlist_infinito(payload: FeedRequest):
    """
    GENERA UN LOTE DE CANCIONES (INFINITE SCROLL)
    """
    try:
        print(f"🔍 Generando lote de {payload.limit} canciones. Excluyendo {len(payload.seen_ids)} ya vistas.")
        
        spotify_service = SpotifyService()
        
        # 1. Obtener Playlist Base (Semillas)
        tracks_origen = spotify_service.enlistar_playlist(payload.playlist_id)
        if not tracks_origen:
            return {"error": "Playlist vacía"}

        # 2. Crear BLACKLIST
        blacklist_ids = set()
        for sid in payload.seen_ids:
            blacklist_ids.add(str(sid))
            
        resultados_finales = []
        conteo_artistas_lote = {} 
        intentos_totales = 0
        MAX_INTENTOS = 15 # Aumenté un poco los intentos por seguridad
        
        async with httpx.AsyncClient(timeout=25.0) as client:
            
            while len(resultados_finales) < payload.limit and intentos_totales < MAX_INTENTOS:
                
                faltan = payload.limit - len(resultados_finales)
                # Solo imprimir cada 3 intentos para no saturar consola
                if intentos_totales % 3 == 0:
                    print(f"--- Buscando... Faltan {faltan} canciones ---")
                
                # A. ELEGIR SEMILLA
                semilla_sp = random.choice(tracks_origen)
                nombre_semilla = semilla_sp.get('name', '')
                try:
                    artista_semilla = semilla_sp['artists'][0]['name']
                except:
                    artista_semilla = ""
                
                # B. BUSCAR SEMILLA EN DEEZER
                query = f'{artista_semilla} {nombre_semilla}'
                search_res = await client.get("https://api.deezer.com/search", params={"q": query, "limit": 1})
                search_data = search_res.json()
                
                if not search_data.get('data'):
                    intentos_totales += 1
                    continue 
                
                deezer_track = search_data['data'][0]
                deezer_id = deezer_track['id']
                deezer_artist_id = deezer_track['artist']['id']

                # C. OBTENER CANDIDATOS
                candidatos_raw = []
                
                # Intento 1: Related
                rel_res = await client.get(f"https://api.deezer.com/track/{deezer_id}/related")
                rel_data = rel_res.json()
                
                if 'data' in rel_data and len(rel_data['data']) > 0:
                    candidatos_raw = rel_data['data']
                else:
                    # Intento 2: Top Artista
                    top_res = await client.get(f"https://api.deezer.com/artist/{deezer_artist_id}/top?limit=30")
                    top_data = top_res.json()
                    if 'data' in top_data:
                        candidatos_raw = top_data['data']

                # D. FILTRADO
                random.shuffle(candidatos_raw)
                
                for track in candidatos_raw:
                    if len(resultados_finales) >= payload.limit:
                        break
                        
                    t_id = str(track['id'])
                    t_artist = track['artist']['name']
                    
                    # Filtros: Blacklist, Repetidos locales, Variedad artista
                    if t_id in blacklist_ids: continue
                    if any(r['id'] == track['id'] for r in resultados_finales): continue
                    
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

        print(f"✅ Lote completado: {len(resultados_finales)} canciones.")
        return resultados_finales

    except Exception as e:
        print(f"ERROR FATAL EN FEED: {str(e)}")
        import traceback
        traceback.print_exc()
        return []
    

# ------------------------------------------------------------------------------------------------------------------------------
# ------- ALGORITMO GENÉTICO ---------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------------------

@app.post("/generar-playlist-inteligente")
async def generar_playlist_inteligente(payload: PlaylistRequest):
    """
    Algoritmo Genético para optimizar playlist basada en audio features
    """
    analyzer = AudioAnalysisService()
    
    print("--- 1. Analizando Target ---")
    target_cromosoma = analyzer.generar_cromosoma(payload.target_track_url)
    
    if target_cromosoma is None:
        return {"error": "No se pudo analizar la canción objetivo (URL inválida o sin audio)"}

    target_list = target_cromosoma.tolist()

    print(f"--- 2. Analizando {len(payload.candidates)} Candidatos ---")
    processed_candidates = []
    
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
        return {"error": "No hay suficientes candidatos válidos (con preview) para armar la playlist."}

    print("--- 3. Ejecutando Algoritmo Genético ---")
    optimizer = GeneticOptimizer(
        population_data=processed_candidates, 
        target_chromosome=target_list
    )
    
    mejor_playlist = optimizer.run()
    
    resultado_limpio = []
    for track in mejor_playlist:
        track_copy = track.copy()
        if 'cromosoma' in track_copy:
            del track_copy['cromosoma']
        resultado_limpio.append(track_copy)

    return {"playlist_generada": resultado_limpio}


@app.post("/crear-playlist-inteligente-auto")
async def auto_smart_playlist(payload: SmartPlaylistRequest):
    """
    1. Crea playlist vacía.
    2. Busca candidatos en Deezer (basado en likes o semilla).
    3. Aplica Algoritmo Genético para seleccionar los mejores 20.
    4. Guarda en DB.
    """
    # 1. Crear Playlist en DB
    from app.models.funciones_db import crear_playlist_db, agregar_cancion_a_playlist_db, obtener_likes_db
    
    id_nueva_playlist = crear_playlist_db(payload.id_usuario, payload.nombre_playlist)
    
    # 2. Obtener Semilla (Target)
    analyzer = AudioAnalysisService()
    target_cromosoma = None
    
    # Si no nos dan semilla, usamos el promedio de sus Likes recientes
    likes = obtener_likes_db(payload.id_usuario)
    if not payload.semilla_id and likes:
        # Usamos el último like como referencia rápida
        last_like = likes[0]
        print(f"Usando semilla de Like: {last_like['titulo']}")
        target_cromosoma = analyzer.generar_cromosoma(last_like['preview'])
        query_artist = last_like['artista']
    else:
        # Default o semilla especifica
        query_artist = "Daft Punk" # Default fallback
        # (Aquí podrías mejorar la lógica para buscar la semilla específica si viene en payload)

    if target_cromosoma is None:
        # Cromosoma dummy si falla todo
        target_cromosoma = np.random.rand(16)

    # 3. Buscar Candidatos (Usamos Deezer Search para traer MUCHOS)
    candidatos_analizados = []
    
    async with httpx.AsyncClient() as client:
        # Buscamos canciones relacionadas al artista semilla
        resp = await client.get(f"https://api.deezer.com/search?q=artist:'{query_artist}'&limit=50")
        data = resp.json()
        
        candidates_raw = data.get('data', [])
        
        # Analizamos audio de los candidatos (Esto toma tiempo, limitamos a 30 para no tardar años)
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

    # 4. Ejecutar Algoritmo Genético
    if len(candidatos_analizados) > 5:
        print("Ejecutando Evolución...")
        optimizer = GeneticOptimizer(
            population_data=candidatos_analizados, 
            target_chromosome=target_cromosoma.tolist(),
            target_size=20 # <--- PEDIMOS 20 CANCIONES
        )
        seleccion_ia = optimizer.run()
    else:
        seleccion_ia = candidatos_analizados # Si hay pocos, guardamos todos

    # 5. Guardar en DB
    for track in seleccion_ia:
        agregar_cancion_a_playlist_db(id_nueva_playlist, track)

    return {"mensaje": "Playlist Generada con Éxito", "total": len(seleccion_ia)}


@app.post("/completar-playlist-ia")
async def completar_playlist_existente(payload: CompletePlaylistRequest):
    """
    Toma las canciones de una playlist existente, analiza su 'vibe' y agrega 5 nuevas.
    Mejorado: Si las canciones no tienen preview (ej. Spotify), busca referencias externas.
    """
    from app.models.funciones_db import obtener_canciones_playlist_db, agregar_cancion_a_playlist_db, obtener_likes_db
    
    analyzer = AudioAnalysisService()
    
    # 1. Obtener canciones actuales de la playlist
    canciones_actuales = obtener_canciones_playlist_db(payload.id_playlist)
    
    target_cromosoma = None
    query_artist = "Daft Punk" # Default de seguridad
    
    # --- A. INTENTO 1: ANALIZAR AUDIO DE LA PLAYLIST ---
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
        
        if cromosomas:
            target_cromosoma = np.mean(cromosomas, axis=0)
            query_artist = validas[0]['artista']

    # --- B. INTENTO 2 (NUEVO): SI HAY CANCIONES PERO SIN AUDIO (Importadas de Spotify) ---
    if target_cromosoma is None and len(canciones_actuales) > 0:
        print("⚠️ Playlist con canciones pero sin audio. Buscando referencia externa...")
        # Tomamos la primera canción como "Semilla"
        ref_track = canciones_actuales[0]
        query_artist = ref_track['artista']
        query_track = ref_track['titulo']
        
        # Buscamos esta canción en Deezer para robarle el cromosoma
        async with httpx.AsyncClient() as client:
            try:
                # Buscamos "Artista Titulo"
                q = f"{query_artist} {query_track}"
                resp = await client.get(f"https://api.deezer.com/search?q={q}&limit=1")
                data = resp.json()
                if data.get('data'):
                    deezer_match = data['data'][0]
                    if deezer_match.get('preview'):
                        print(f"✅ Referencia encontrada en Deezer: {deezer_match['title']}")
                        target_cromosoma = analyzer.generar_cromosoma(deezer_match['preview'])
            except Exception as e:
                print(f"Error buscando referencia: {e}")

    # --- C. INTENTO 3: FALLBACK A ME GUSTA ---
    if target_cromosoma is None:
        print("Playlist vacía o imposible de analizar. Usando 'Me Gusta'...")
        likes = obtener_likes_db(payload.id_usuario)
        if likes:
            last = likes[0]
            if last.get('preview'): # Solo si el like tiene preview
                target_cromosoma = analyzer.generar_cromosoma(last['preview'])
                query_artist = last['artista']
    
    # Si después de todo sigue siendo None, error
    if target_cromosoma is None:
        raise HTTPException(status_code=400, detail="No se pudo analizar la playlist (sin audio) ni se encontraron likes válidos.")

    # 3. BUSCAR CANDIDATOS (Deezer)
    candidatos_analizados = []
    ids_existentes = set(str(c['id_externo']) for c in canciones_actuales)

    async with httpx.AsyncClient() as client:
        # Buscamos tracks relacionados al artista detectado
        print(f"Buscando candidatos similares a: {query_artist}")
        resp = await client.get(f"https://api.deezer.com/search?q=artist:'{query_artist}'&limit=50")
        data = resp.json()
        raw = data.get('data', [])
        
        for track in raw:
            # Filtros básicos
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
                
                if len(candidatos_analizados) >= 15: break 

    # 4. ALGORITMO GENÉTICO
    if not candidatos_analizados:
         return {"mensaje": "No se encontraron candidatos suficientes."}

    optimizer = GeneticOptimizer(
        population_data=candidatos_analizados, 
        target_chromosome=target_cromosoma.tolist(),
        target_size=5 
    )
    seleccion = optimizer.run()

    # 5. GUARDAR
    count = 0
    for track in seleccion:
        track_db = track.copy()
        if agregar_cancion_a_playlist_db(payload.id_playlist, track_db):
            count += 1

    return {"mensaje": "Completado con éxito", "agregadas": count}