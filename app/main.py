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