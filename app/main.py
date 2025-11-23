import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
from fastapi import FastAPI
from app.services.spotify_service import SpotifyService
from app.services.audio_analysis import AudioAnalysisService  
from dotenv import load_dotenv
load_dotenv()

app = FastAPI()

#Credenciales de Spotify



#middleware

#Coonfig CORS
#vite react
#Conectar routers

@app.get("/")
def inicio():
    return "Hola"

@app.get("/playlist-tracks/{PLAYLIST_ID}")
def top_tracks(PLAYLIST_ID: str):
    spotify_service = SpotifyService()
    #PLAYLIST_ID = "6GjULfC3dnq103KCta8plp"
    resultado = spotify_service.enlistar_playlist(PLAYLIST_ID)
    return resultado

@app.get("/datos-cancion/{TRACK_ID}")
def datos_cancion(TRACK_ID: str):
    spotify_service = SpotifyService()
    #TRACK_ID = "3hqCFeuaSOPov7JdWaTjST"
    resultado = spotify_service.leer_datos_cancion(TRACK_ID)
    return resultado

'''
@app.get("/audio-features/{TRACK_ID}")
def audio_features(TRACK_ID: str):
    spotify_service = SpotifyService()
    #TRACK_ID = "3hqCFeuaSOPov7JdWaTjST"
    resultado = spotify_service.obtener_audio_features(TRACK_ID)
    return resultado

@app.get("/preview_audio/{TRACK_ID}")
def preview_audio(TRACK_ID: str):
    spotify_service = SpotifyService()
    #TRACK_ID = "3hqCFeuaSOPov7JdWaTjST"
    resultado = spotify_service.obtener_preview_url(TRACK_ID)
    return resultado
'''

@app.get("/nombre-cancion/{TRACK_ID}")
def nombre_cancion(TRACK_ID: str):
    spotify_service = SpotifyService()
    #TRACK_ID = "3hqCFeuaSOPov7JdWaTjST"
    resultado = spotify_service.obtener_nombre_cancion(TRACK_ID)
    return resultado

@app.get("/artista-cancion/{TRACK_ID}")
def artista_cancion(TRACK_ID: str):
    spotify_service = SpotifyService()
    #TRACK_ID = "3hqCFeuaSOPov7JdWaTjST"
    resultado = spotify_service.obtener_artista(TRACK_ID)
    return resultado

@app.get("/preview/{TRACK_ID}")
def preview(TRACK_ID: str):
    spotify_service = SpotifyService()
    #TRACK_ID = "3hqCFeuaSOPov7JdWaTjST"
    resultado = spotify_service.obtener_url_preview(TRACK_ID)
    return resultado

'''
@app.get("/get_audio/{URL_CANCION}")
def get_audio(URL_CANCION: str):
    audio_analisis = AudioAnalysisService()
    resultado = audio_analisis.convertir_cancion(URL_CANCION)
    return resultado
'''

@app.get("/features/") 
def get_features(url_cancion: str): 
    audio_analisis = AudioAnalysisService()
    
    print(f"Procesando URL: {url_cancion}") 
    resultado = audio_analisis.generar_cromosoma(url_cancion)
    
    #numpy array a lista normalpara el envío en JSON
    if resultado is not None:
        return {"cromosoma": resultado.tolist()} 
    else:
        return {"error": "No se pudo procesar el audio"}