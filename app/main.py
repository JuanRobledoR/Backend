import spotipy
import random
import asyncio
from spotipy.oauth2 import SpotifyOAuth
import os
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.services.spotify_service import SpotifyService
from app.services.audio_analysis import AudioAnalysisService  
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Credenciales de Spotify
# (Se cargan desde variables de entorno o tu servicio)

# Coonfig CORS vite react
origins = [
    "http://localhost:5173",
]

# Middleware
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
    return "Hola"

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

@app.get("/nombre-cancion/{TRACK_ID}")
def nombre_cancion(TRACK_ID: str):
    spotify_service = SpotifyService()
    resultado = spotify_service.obtener_nombre_cancion(TRACK_ID)
    return resultado

@app.get("/artista-cancion/{TRACK_ID}")
def artista_cancion(TRACK_ID: str):
    spotify_service = SpotifyService()
    resultado = spotify_service.obtener_artista(TRACK_ID)
    return resultado

@app.get("/preview/{TRACK_ID}")
def preview(TRACK_ID: str):
    spotify_service = SpotifyService()
    resultado = spotify_service.obtener_url_preview(TRACK_ID)
    return resultado

@app.get("/features/") 
def get_features(url_cancion: str): 
    audio_analisis = AudioAnalysisService()
    
    print(f"Procesando URL: {url_cancion}") 
    resultado = audio_analisis.generar_cromosoma(url_cancion)
    
    # numpy array a lista normal para el envío en JSON
    if resultado is not None:
        return {"cromosoma": resultado.tolist()} 
    else:
        return {"error": "No se pudo procesar el audio"}

@app.get("/buscar")
async def buscar_cancion(q: str):
    if not q:
        return []
    
    # Usamos httpx para hablar con Deezer
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


# --- Feed insano infinito ---

@app.get("/feed-playlist/{playlist_id}")
async def feed_playlist(playlist_id: str, offset: int = 0, limit: int = 10):
    """
    Obtiene la playlist completa de Spotify, selecciona 10 canciones 
    TOTALMENTE AL AZAR y busca sus equivalentes en Deezer.
    """
    try:
        print(f"Obteniendo playlist de Spotify: {playlist_id}")
        spotify_service = SpotifyService()
        
        # 1. Obtener lista COMPLETA de Spotify
        tracks_spotify = spotify_service.enlistar_playlist(playlist_id)
        
        if not tracks_spotify:
            print("ERROR:La playlist de Spotify está vacía.")
            return []

        # 2. SELECCIÓN ALEATORIA (Aquí está el cambio que pediste)
        # En lugar de cortar por offset, tomamos una muestra aleatoria.
        print(f"Seleccionando {limit} canciones al azar de un total de {len(tracks_spotify)}...")
        
        lote_spotify = []
        if len(tracks_spotify) > limit:
            # random.sample toma elementos únicos sin repetir en esta tirada
            lote_spotify = random.sample(tracks_spotify, limit)
        else:
            # Si hay pocas canciones (menos de 10), las tomamos todas y las revolvemos
            lote_spotify = list(tracks_spotify)
            random.shuffle(lote_spotify)
        
        print(f"Buscando {len(lote_spotify)} canciones seleccionadas en Deezer...")

        # --- FUNCIÓN AUXILIAR BLINDADA (Se mantiene igual) ---
        async def buscar_en_deezer(client, track_sp):
            query = "Desconocido" 
            try:
                # DETECTAMOS QUÉ NOS MANDÓ SPOTIFY
                if isinstance(track_sp, str):
                    query = track_sp
                elif isinstance(track_sp, dict):
                    if 'track' in track_sp:
                        nombre = track_sp['track'].get('name', '')
                        artista = track_sp['track']['artists'][0].get('name', '') if track_sp['track'].get('artists') else ''
                    else:
                        nombre = track_sp.get('name', '')
                        artista = track_sp.get('artists', [{}])[0].get('name', '')
                    
                    query = f"{artista} {nombre}".strip()
                else:
                    query = str(track_sp)

                if not query or query == " ":
                    return None

                # Búsqueda en Deezer
                response = await client.get(f"https://api.deezer.com/search?q={query}&limit=1")
                data = response.json()

                if "data" in data and len(data["data"]) > 0:
                    t = data["data"][0]
                    return {
                        "id": t["id"],
                        "titulo": t["title"],
                        "artista": t["artist"]["name"],
                        "imagen": t["album"]["cover_xl"], 
                        "preview": t["preview"] 
                    }
            except Exception as e:
                print(f" ---> Error buscando '{query}': {e}")
            return None

        # --- EJECUCIÓN PARALELA ---
        resultados = []
        async with httpx.AsyncClient() as client:
            tareas = [buscar_en_deezer(client, track) for track in lote_spotify]
            deezer_results = await asyncio.gather(*tareas)
            resultados = [r for r in deezer_results if r is not None]

        print(f"Se encontraron {len(resultados)} canciones en Deezer para enviar al front.")
        
        return resultados

    except Exception as e:
        print(f"ERROR GENERAL: {str(e)}")
        import traceback
        traceback.print_exc()
        return []